from copy import deepcopy
from math import inf
import pickle
import random
from time import perf_counter

import pytest

from agents import GreedyAgent, MinimaxAgent, RandomAgent
from agents.minimax_agent import Observation
from domino.actions import DrawAction, PassAction, PlayAction
from domino.game import Game
from domino.player import Player
from domino.tile import Tile
from domino.history import PublicAction
from interfaces.cli import CLI


def position():
    game = Game()
    game.players = [Player("P1", [Tile((6, 1)), Tile((1, 2))]),
                    Player("P2", [Tile((6, 3)), Tile((4, 4))])]
    game.table.add_first_tile(Tile((6, 6)))
    return game


class HiddenTiles(list):
    """Permite contar peças; qualquer leitura do conteúdo denuncia vazamento."""

    def __iter__(self):
        raise AssertionError("A IA tentou ler peças ocultas")

    def __getitem__(self, key):
        raise AssertionError("A IA tentou ler peças ocultas")


def test_hidden_hands_and_stock_are_never_read():
    game = position()
    game.players[1].tiles = HiddenTiles(game.players[1].tiles)
    game.stock = HiddenTiles([Tile((0, 0)), Tile((0, 1))])
    game.has_stock = True
    game.public_history = [PublicAction(1, "draw", (6, 6))]
    assert isinstance(MinimaxAgent(seed=1).choose_action(game), PlayAction)


def test_same_public_information_gives_same_decision():
    first = Game()
    first.start_round(n_players=2, tile_count=7)
    second = deepcopy(first)
    other = 1 - first.current_player_index
    # Redistribui peças reais ocultas, mantendo todas as informações públicas.
    second.players[other].tiles[0], second.stock[0] = second.stock[0], second.players[other].tiles[0]
    second.stock.reverse()
    assert Observation.from_game(first) == Observation.from_game(second)
    options = dict(seed=2, time_limit=10, max_nodes=1000)
    assert MinimaxAgent(**options).choose_action(first) == MinimaxAgent(**options).choose_action(second)


def test_choice_does_not_mutate_game():
    game = position()
    before = pickle.dumps(game)
    MinimaxAgent(seed=3).choose_action(game)
    assert pickle.dumps(game) == before


def test_sample_preserves_public_table_and_piece_counts():
    game = Game()
    game.start_round(n_players=2, tile_count=7)
    game.apply_action(PlayAction(0, "right"))
    observation = Observation.from_game(game)
    sample = MinimaxAgent(seed=4)._sample_game(observation)
    assert tuple(tuple(t) for t in sample.players[0].tiles) == observation.hand
    assert len(sample.players[1].tiles) == observation.opponent_counts[0]
    assert len(sample.stock) == observation.stock_count
    assert tuple(tuple(t) for t in sample.table.tiles_deque) == observation.table
    tiles = [t for p in sample.players for t in p.tiles] + sample.stock + list(sample.table.tiles_deque)
    assert len(tiles) == 28
    assert len({tuple(sorted(t)) for t in tiles}) == 28


def exhaustive(agent, game, depth):
    if depth == 0 or game.round_over:
        return agent._evaluate(game)
    scores = []
    for action in agent._actions(game):
        child = deepcopy(game)
        child.apply_action(action)
        scores.append(exhaustive(agent, child, depth - 1))
    return (max if game.current_player_index == 0 else min)(scores)


@pytest.mark.parametrize("turn", [0, 1])
def test_alpha_beta_matches_exhaustive_minimax(turn):
    game = position()
    game.current_player_index = turn
    agent = MinimaxAgent(max_nodes=100000, time_limit=10)
    agent._deadline = perf_counter() + 10
    agent.last_stats = {"nodes": 0, "cutoffs": 0}
    expected = exhaustive(agent, game, 5)
    assert agent._search(game, 5, -inf, inf) == expected


def test_immediate_win_is_preferred():
    game = position()
    game.players[0].tiles = [Tile((6, 1))]
    action = MinimaxAgent(seed=1).choose_action(game)
    game.apply_action(action)
    assert game.round_over
    assert game.winner is game.players[0]


def test_alpha_beta_prunes_without_changing_value():
    observation = Observation(
        ((6, 6), (6, 5), (5, 5), (4, 3), (2, 1), (0, 0), (3, 3)),
        (), (7,), 14, True, False)
    agent = MinimaxAgent(seed=16, max_nodes=100000, time_limit=10)
    game = agent._sample_game(observation)
    agent._deadline = perf_counter() + 10
    agent.last_stats = {"nodes": 0, "cutoffs": 0}
    expected = exhaustive(agent, game, 4)
    assert agent._search(game, 4, -inf, inf) == expected
    assert agent.last_stats["cutoffs"] > 0


def test_small_budget_still_returns_legal_action():
    game = position()
    agent = MinimaxAgent(max_nodes=1, seed=0)
    action = agent.choose_action(game)
    assert agent.last_stats["nodes"] <= 1
    assert agent.last_stats["samples"] == 0
    game.apply_action(action)


def test_draw_until_playable_or_stock_empty():
    game = position()
    game.players[0].tiles = [Tile((1, 1))]
    game.has_stock = True
    game.stock = [Tile((6, 2)), Tile((0, 0)), Tile((2, 3))]
    agent = MinimaxAgent(seed=1)
    for remaining in (2, 1, 0):
        assert isinstance(agent.choose_action(game), DrawAction)
        game.apply_action(DrawAction())
        assert len(game.stock) == remaining
        assert game.current_player_index == 0
    action = agent.choose_action(game)
    assert isinstance(action, PlayAction)
    game.apply_action(action)


def test_pass_after_unhelpful_stock_exhausted():
    game = position()
    game.players[0].tiles = [Tile((1, 1))]
    game.has_stock = True
    game.stock = [Tile((0, 0))]
    agent = MinimaxAgent()
    game.apply_action(agent.choose_action(game))
    assert isinstance(agent.choose_action(game), PassAction)
    game.apply_action(agent.choose_action(game))
    assert game.current_player_index == 1


@pytest.mark.parametrize("opponent", [RandomAgent, GreedyAgent])
@pytest.mark.parametrize("has_stock", [False, True])
def test_complete_round_against_existing_agents(opponent, has_stock):
    state = random.getstate()
    random.seed(7)
    try:
        game = Game()
        game.start_round(n_players=2, tile_count=7, has_stock=has_stock)
        minimax = MinimaxAgent(seed=7, samples=2, max_nodes=600)
        agents = [minimax, opponent()]
        for _ in range(200):
            if game.round_over:
                break
            game.apply_action(agents[game.current_player_index].choose_action(game))
            tiles = ([t for p in game.players for t in p.tiles] + game.stock
                     + game.tiles + list(game.table.tiles_deque))
            assert len(tiles) == 28
            assert len({tuple(sorted(t)) for t in tiles}) == 28
        assert game.round_over
    finally:
        random.setstate(state)


def test_rejects_more_than_four_players():
    game = Game()
    game.start_round(n_players=4)
    game.players.append(Player("extra", [Tile((0, 0))]))
    with pytest.raises(ValueError, match="quatro"):
        MinimaxAgent().choose_action(game)


def test_configuration_no_longer_offers_single_draw(monkeypatch):
    responses = iter(["2", "7", "s"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    assert CLI().ask_configuration() == (2, 7, True, False)


@pytest.mark.parametrize("n_players", [2, 3, 4])
def test_menu_selects_minimax(monkeypatch, n_players):
    monkeypatch.setattr("builtins.input", lambda _: "3")
    assert isinstance(CLI().ask_agent_type(n_players), MinimaxAgent)
