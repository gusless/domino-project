from __future__ import annotations
from typing import TYPE_CHECKING
import random

from .actions import DrawAction, PassAction, PlayAction
from . import rules
from .player import Player
from .table import Table
from .tile import Tile
from .history import PublicAction

# if TYPE_CHECKING:
#     from controllers.controller import Controller



class Game:
    """Controla o estado e as operações de uma partida de dominó."""

    def __init__(self):
        self.players: list[Player] = []
        self.tiles: list[Tile] = []
        self.stock: list[Tile] = []
        self.table = Table()

        self.current_player_index = 0
        self.has_stock = False
        self.pull_one = False

        self.round_over = False
        self.winner: Player | None = None
        self.draw_result: Tile | None = None
        self.public_history: list[PublicAction] = []

    @staticmethod
    def make_tiles() -> list[Tile]:
        return [
            Tile((left, right))
            for left in range(7)
            for right in range(left, 7)
        ]

    @staticmethod
    def get_generic_doubles(tiles: list[Tile] | None = None) -> list[Tile]:
        source = Game.make_tiles() if tiles is None else tiles
        return [tile for tile in source if tile.is_double]

    @staticmethod
    def get_generic_not_doubles(tiles: list[Tile] | None = None) -> list[Tile]:
        source = Game.make_tiles() if tiles is None else tiles
        return [tile for tile in source if not tile.is_double]

    @staticmethod
    def get_generic_prioritized_tiles(tiles: list[Tile] | None = None) -> list[Tile]:
        source = Game.make_tiles() if tiles is None else tiles
        doubles = sorted(
            Game.get_generic_doubles(source),
            key=lambda tile: sum(tile),
            reverse=True,
        )
        non_doubles = sorted(
            Game.get_generic_not_doubles(source),
            key=lambda tile: sum(tile),
            reverse=True,
        )
        return doubles + non_doubles

    def start_round(
        self,
        n_players: int = 4,
        tile_count: int = 7,
        has_stock: bool = True,
        pull_one: bool = False,
        #controllers: list[Controller] | None = None,
    ) -> None:
        # if not controllers:
        #     raise ValueError("Falta de Controller")
        if not 2 <= n_players <= 4:
            raise ValueError("Só é permitido jogar com 2 a 4 jogadores.")
        if tile_count < 5 or tile_count * n_players > 28:
            raise ValueError("Quantidade de peças por jogador inválida.")
        # if len(controllers) != n_players:
        #     raise ValueError("A quantidade de Controllers deve corresponder aos jogadores.")

        self.tiles = self.make_tiles()
        random.shuffle(self.tiles)

        previous_wins = {
            player.name: player.wins
            for player in self.players
        }

        # vejo isso depois
        # if len(self.players) != n_players:
        #     self.players = []
        #     player_idx = 1
        #     com_idx = 1

        #     for controller in controllers:
        #         if isinstance(controller, HumanController):
        #             name = f"P{player_idx}"
        #             player_idx += 1
        #         elif isinstance(controller, AgentController):
        #             name = f"COM{com_idx}"
        #             com_idx += 1
        #         else:
        #             raise TypeError("Controller desconhecido.")

        #         self.players.append(Player(name, []))

        if len(self.players) != n_players:
            self.players = [
                Player(f"P{i + 1}", [])
                for i in range(n_players)
            ]

        for player in self.players:
            player.tiles = [
                self.tiles.pop()
                for _ in range(tile_count)
            ]


        self.has_stock = has_stock
        self.pull_one = pull_one

        if has_stock:
            self.stock = self.tiles.copy()
            self.tiles.clear()
        else:
            self.stock = []

        self.table = Table()
        self.current_player_index = 0
        self.round_over = False
        self.winner = None
        self.draw_result = None

        self.public_history = []
        self._select_starter()

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]

    def _select_starter(self) -> None:
        prioritized_tiles = self.get_generic_prioritized_tiles()

        for tile in prioritized_tiles:
            for index, player in enumerate(self.players):
                if tile in player.tiles:
                    self.current_player_index = index
                    return

        self.current_player_index = random.randrange(len(self.players))

    def get_playable_indices(self, player: Player | None = None) -> list[int]:
        return rules.get_playable_indices(player or self.current_player, self.table)

    def apply_action(self, action: PlayAction | DrawAction | PassAction) -> None:
        if self.round_over:
            raise RuntimeError("A rodada já terminou.")

        player = self.current_player
        actor = self.current_player_index
        endpoints = self.table.get_sides()

        if isinstance(action, PlayAction):
            self._play(player, action)
            # A peça já foi removida da mão e está visível na mesa.
            tile = self.table.tiles_deque[0 if action.side == "left" else -1]
            event = PublicAction(actor, "play", endpoints, tuple(tile))
        elif isinstance(action, DrawAction):
            self._draw(player)
            event = PublicAction(actor, "draw", endpoints)
        elif isinstance(action, PassAction):
            self._pass(player)
            self._advance_turn()
            event = PublicAction(actor, "pass", endpoints)
        else:
            raise TypeError("Tipo de ação desconhecido.")

        self.public_history.append(event)
        self._check_round_end()

    def _play(self, player: Player, action: PlayAction) -> None:
        if not 0 <= action.tile_index < len(player.tiles):
            raise IndexError("Índice de peça inválido.")

        if action.tile_index not in rules.get_playable_indices(player, self.table):
            raise ValueError("Essa peça não pode ser jogada.")

        tile = player.tiles[action.tile_index]
        if not rules.can_place(tile, self.table, action.side):
            raise ValueError("A peça não encaixa no lado escolhido.")

        if not self.table.tiles_deque:
            self.table.add_first_tile(tile)
        elif action.side == "left":
            self.table.add_left(tile)
        else:
            self.table.add_right(tile)

        player.tiles.pop(action.tile_index)
        self.draw_result = None
        if not self.round_over:
            self._advance_turn()

    def _draw(self, player: Player) -> None:
        if not self.has_stock:
            raise ValueError("Esta rodada não permite comprar peças.")
        if rules.can_play(player, self.table):
            raise ValueError("Você já possui uma peça que pode ser jogada.")
        if not self.stock:
            raise ValueError("Não há peças para comprar.")

        tile = self.stock.pop()
        player.tiles.append(tile)

        self.draw_result = tile

        # se so pode puxar uma
        if self.pull_one and not rules.can_play(player, self.table):
            self._advance_turn()

    def _pass(self, player: Player) -> None:
        if self.stock:
            raise ValueError("Ainda existem peças para comprar.")
        if rules.can_play(player, self.table):
            raise ValueError("Você possui uma peça que pode ser jogada.")

    def _advance_turn(self) -> None:
        self.current_player_index = (self.current_player_index + 1) % len(self.players)

    def _check_round_end(self) -> None:
        winner = rules.get_winner(self.players)
        if winner is not None:
            self.winner = winner
            self.winner.wins += 1
            self.round_over = True
            return

        if rules.is_game_locked(self.players, self.table, self.stock, self.has_stock):
            self.winner = rules.get_player_with_fewer_points(self.players)
            if self.winner is not None:
                self.winner.wins += 1
            self.round_over = True

    def get_round_ranking(self) -> list[Player]:
        return sorted(self.players, key=lambda player: player.get_tile_points())

    def get_match_ranking(self) -> list[Player]:
        return sorted(self.players, key=lambda player: player.wins, reverse=True)
