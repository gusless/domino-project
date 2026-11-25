"""Minimax/Max-n sobre hipóteses, sem acesso às peças ocultas reais."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import inf
import random
from time import perf_counter

from .base import BaseAgent
from domino import rules
from domino.actions import Action, DrawAction, PassAction, PlayAction
from domino.game import Game
from domino.player import Player
from domino.tile import Tile
from domino.history import PublicAction


@dataclass(frozen=True)
class Observation:
    """Somente a mão própria e informações públicas da rodada."""

    hand: tuple[tuple[int, int], ...]
    table: tuple[tuple[int, int], ...]
    opponent_counts: tuple[int, ...]
    stock_count: int
    has_stock: bool
    pull_one: bool
    history: tuple[PublicAction, ...] = ()
    own_index: int = 0

    @classmethod
    def from_game(cls, game: Game) -> Observation:
        if not 2 <= len(game.players) <= 4:
            raise ValueError("MinimaxAgent suporta de dois a quatro jogadores.")
        if game.round_over:
            raise ValueError("A rodada já terminou.")
        own = game.current_player_index
        return cls(
            tuple(tuple(tile) for tile in game.players[own].tiles),
            tuple(tuple(tile) for tile in game.table.tiles_deque),
            tuple(len(game.players[(own + offset) % len(game.players)].tiles)
                  for offset in range(1, len(game.players))), len(game.stock),
            game.has_stock, game.pull_one,
            tuple(game.public_history), own,
        )

    def hand_constraints(self, player_index: int | None = None) -> tuple[tuple[frozenset[int], int], ...]:
        """Limites de peças com certos números, deduzidos de eventos públicos.

        Após uma ausência de encaixe, somente compras posteriores podem trazer
        os números ausentes. Jogadas posteriores com esses números consomem
        essas compras. Não se mantém uma proibição absoluta após comprar.
        """
        n_players = len(self.opponent_counts) + 1
        if player_index is None:
            player_index = (self.own_index + 1) % n_players
        offset = (player_index - self.own_index) % n_players
        if not 0 <= player_index < n_players or offset == 0:
            raise ValueError("As restrições devem se referir a um adversário.")
        count = self.opponent_counts[offset - 1]
        draws = 0
        played = []
        limits = {}
        for event in reversed(self.history):
            if event.player_index != player_index:
                continue
            if event.kind == "play" and event.tile is not None:
                played.append(event.tile)
            elif event.kind in ("draw", "pass"):
                if event.kind == "draw":
                    draws += 1  # Inclui a compra feita logo após a ausência.
                numbers = frozenset(n for n in event.endpoints if n is not None)
                if numbers:
                    maximum = draws - sum(bool(numbers.intersection(t)) for t in played)
                    maximum = max(0, maximum)
                    limits[numbers] = min(limits.get(numbers, maximum), maximum)
        return tuple((numbers, limit) for numbers, limit in limits.items()
                     if limit < count)


class _SearchLimit(Exception):
    pass


class MinimaxAgent(BaseAgent):
    """Busca limitada em mãos hipotéticas; não resolve o jogo de informação oculta.

    Em modo automático, usa Minimax com Alfa-Beta para dois jogadores e Max-n
    para três/quatro. Paranoid permanece como referência interna de benchmark.
    A média das avaliações orienta a jogada real. O histórico público restringe
    as hipóteses, sem acesso à identidade de peças compradas pelo adversário.
    """

    def __init__(self, depth=3, samples=6, max_nodes=2500, time_limit=0.2, seed=None,
                 strategy="auto"):
        if depth < 1 or samples < 1 or max_nodes < 1 or time_limit <= 0:
            raise ValueError("Os limites de busca devem ser positivos.")
        self.depth = depth
        self.samples = samples
        self.max_nodes = max_nodes
        self.time_limit = time_limit
        if strategy not in ("auto", "paranoid", "maxn"):
            raise ValueError("Estratégia deve ser auto, paranoid ou maxn.")
        self.strategy = strategy
        self.rng = random.Random(seed)
        self.last_stats = {}

    def choose_action(self, game: Game) -> Action:
        return self.choose_observation(Observation.from_game(game))

    def choose_play(self, game: Game, playable: list[int]) -> Action:
        return self.choose_action(game)

    def select_side(self, tile: Tile, table) -> str:
        return "right" if rules.can_place(tile, table, "right") else "left"

    def _sample_game(self, observation: Observation) -> Game:
        known = {tuple(sorted(t)) for t in observation.hand + observation.table}
        unknown = [(a, b) for a in range(7) for b in range(a, 7)
                   if (a, b) not in known]
        if not 1 <= len(observation.opponent_counts) <= 3:
            raise ValueError("A observação deve ter de um a três adversários.")
        if any(count < 0 for count in observation.opponent_counts) or observation.stock_count < 0:
            raise ValueError("Contagens de peças inválidas.")
        if sum(observation.opponent_counts) + observation.stock_count > len(unknown):
            raise ValueError("Contagens de peças inconsistentes.")
        self.rng.shuffle(unknown)
        n_players = len(observation.opponent_counts) + 1
        constraints = [observation.hand_constraints((observation.own_index + offset) % n_players)
                       for offset in range(1, n_players)]
        hands, rest = self._distribute(unknown, observation.opponent_counts, constraints)
        game = Game()
        # Normaliza a perspectiva: IA na posição 0, demais em ordem de turno.
        game.players = [Player("IA", [Tile(t) for t in observation.hand])]
        game.players.extend(Player(f"Adversário {i + 1}", [Tile(t) for t in hand])
                            for i, hand in enumerate(hands))
        game.stock = [Tile(t) for t in rest[:observation.stock_count]]
        game.tiles = [Tile(t) for t in rest[observation.stock_count:]]
        game.has_stock = observation.has_stock
        game.pull_one = observation.pull_one
        # Recria a mesa pública, preservando a orientação das peças.
        game.table.tiles_deque.extend(Tile(t) for t in observation.table)
        if observation.table:
            game.table.left_side = observation.table[0][0]
            game.table.right_side = observation.table[-1][1]
        return game

    def _distribute(self, unknown, counts, constraints):
        def allowed(hand, restrictions):
            return all(sum(bool(numbers.intersection(t)) for t in hand) <= limit
                       for numbers, limit in restrictions)

        def split():
            hands = []
            cursor = 0
            for count in counts:
                hands.append(unknown[cursor:cursor + count])
                cursor += count
            return hands, unknown[cursor:]

        # Rejeição mantém amostras uniformes quando as restrições são leves.
        for _ in range(64):
            if perf_counter() >= getattr(self, "_deadline", inf):
                raise _SearchLimit
            hands, rest = split()
            if all(allowed(hand, restrictions) for hand, restrictions in zip(hands, constraints)):
                return hands, rest
            self.rng.shuffle(unknown)

        # Restrições fortes: procura um subconjunto válido com orçamento finito.
        # Essa recuperação não é uma amostragem uniforme da distribuição posterior.
        remaining = 4096
        order = sorted(range(len(counts)),
                       key=lambda i: sum(7 - limit for _, limit in constraints[i]), reverse=True)
        assigned = [[] for _ in counts]

        def assign(position, pool, start=0, hand=None):
            nonlocal remaining
            remaining -= 1
            if remaining < 0 or perf_counter() >= getattr(self, "_deadline", inf):
                raise _SearchLimit
            if position == len(order):
                return [list(h) for h in assigned], pool
            player = order[position]
            if hand is None:
                hand = []
            count = counts[player]
            if len(hand) == count:
                assigned[player] = hand
                selected = set(hand)
                rest = [tile for tile in pool if tile not in selected]
                return assign(position + 1, rest)
            if len(pool) - start < count - len(hand):
                return None
            for index in range(start, len(pool)):
                candidate = hand + [pool[index]]
                if allowed(candidate, constraints[player]):
                    found = assign(position, pool, index + 1, candidate)
                    if found is not None:
                        return found
            return None

        result = assign(0, unknown)
        if result is None:
            raise _SearchLimit
        hands, rest = result
        self.rng.shuffle(rest)
        return hands, rest

    @staticmethod
    def _actions(game: Game) -> list[Action]:
        playable = game.get_playable_indices()
        if not playable:
            return [DrawAction()] if game.has_stock and game.stock else [PassAction()]
        actions = []
        for index in sorted(playable, key=lambda i: sum(game.current_player.tiles[i]), reverse=True):
            for side in ("right", "left"):
                if rules.can_place(game.current_player.tiles[index], game.table, side):
                    actions.append(PlayAction(index, side))
                    if not game.table.tiles_deque:
                        break
        return actions

    @staticmethod
    def _evaluate(game: Game) -> float:
        if game.round_over:
            if game.winner is None:
                return 0.0
            return 10000.0 if game.winner is game.players[0] else -10000.0
        own = game.players[0]
        # Avalia a maior ameaça individual; não soma adversários como se fossem
        # uma dupla no resultado real. Com dois jogadores preserva a fórmula.
        return min(20 * (len(other.tiles) - len(own.tiles))
                + other.get_tile_points() - own.get_tile_points()
                + 2 * (len(game.get_playable_indices(own))
                       - len(game.get_playable_indices(other)))
                   for other in game.players[1:])

    def _search(self, game: Game, depth: int, alpha: float, beta: float) -> float:
        if self.last_stats["nodes"] >= self.max_nodes or perf_counter() >= self._deadline:
            raise _SearchLimit
        self.last_stats["nodes"] += 1
        if game.round_over or depth == 0:
            return self._evaluate(game)
        maximize = game.current_player_index == 0
        value = -inf if maximize else inf
        for action in self._actions(game):
            child = deepcopy(game)
            child.apply_action(action)
            score = self._search(child, depth - 1, alpha, beta)
            if maximize:
                value = max(value, score)
                alpha = max(alpha, value)
            else:
                value = min(value, score)
                beta = min(beta, value)
            if beta <= alpha:
                self.last_stats["cutoffs"] += 1
                break
        return value

    @staticmethod
    def _evaluate_vector(game: Game) -> tuple[float, ...]:
        """Uma utilidade por jogador; cada um busca melhorar a sua própria."""
        if game.round_over:
            return tuple(0.0 if game.winner is None else
                         10000.0 if game.winner is player else -10000.0
                         for player in game.players)
        points = [player.get_tile_points() for player in game.players]
        mobility = [len(game.get_playable_indices(player)) for player in game.players]
        return tuple(min(20 * (len(other.tiles) - len(player.tiles))
                         + points[j] - points[i] + 2 * (mobility[i] - mobility[j])
                         for j, other in enumerate(game.players) if i != j)
                     for i, player in enumerate(game.players))

    def _search_maxn(self, game: Game, depth: int) -> tuple[float, ...]:
        if self.last_stats["nodes"] >= self.max_nodes or perf_counter() >= self._deadline:
            raise _SearchLimit
        self.last_stats["nodes"] += 1
        if game.round_over or depth == 0:
            return self._evaluate_vector(game)
        actor = game.current_player_index
        best = None
        for action in self._actions(game):
            child = deepcopy(game)
            child.apply_action(action)
            scores = self._search_maxn(child, depth - 1)
            # Empates mantêm a primeira ação, na mesma ordenação do paranoid.
            # Não aplica Alfa-Beta de dois jogadores a vetores Max-n.
            if best is None or scores[actor] > best[actor]:
                best = scores
        assert best is not None, "Uma posição não terminal deve permitir uma ação."
        return best

    def choose_observation(self, observation: Observation) -> Action:
        start = perf_counter()
        self._deadline = start + self.time_limit
        self.last_stats = {"nodes": 0, "cutoffs": 0, "samples": 0}
        use_maxn = self.strategy in ("auto", "maxn") and len(observation.opponent_counts) > 1
        self.last_stats["strategy"] = "maxn" if use_maxn else "paranoid"
        # A reserva legal depende só da mão própria e da mesa pública. Assim,
        # esgotar o orçamento ao gerar uma hipótese nunca força uma mão inválida.
        public = Game()
        public.players = [Player("IA", [Tile(t) for t in observation.hand])]
        public.table.tiles_deque.extend(Tile(t) for t in observation.table)
        if observation.table:
            public.table.left_side = observation.table[0][0]
            public.table.right_side = observation.table[-1][1]
        public.has_stock = observation.has_stock
        # Apenas a existência do monte é necessária para gerar uma DrawAction.
        public.stock = [Tile((0, 0))] if observation.stock_count else []
        actions = self._actions(public)
        totals = [0.0] * len(actions)
        best = actions[0]  # Jogada legal de reserva se o orçamento acabar.
        try:
            if len(actions) > 1:
                for index in range(self.samples):
                    sample = self._sample_game(observation)
                    scores = []
                    for action in actions:
                        child = deepcopy(sample)
                        child.apply_action(action)
                        # Janela completa por ação: médias exigem valores exatos,
                        # e não apenas limites produzidos pela poda na raiz.
                        scores.append(self._search_maxn(child, self.depth - 1)[0] if use_maxn
                                      else self._search(child, self.depth - 1, -inf, inf))
                    # Descarta uma hipótese incompleta para não favorecer ações
                    # que receberam mais tempo de busca que as demais.
                    totals = [total + score for total, score in zip(totals, scores)]
                    self.last_stats["samples"] += 1
                    best = actions[max(range(len(actions)), key=totals.__getitem__)]
        except _SearchLimit:
            pass
        self.last_stats["seconds"] = perf_counter() - start
        return best
