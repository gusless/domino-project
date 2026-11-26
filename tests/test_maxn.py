from copy import deepcopy
from math import inf
from time import perf_counter

import pytest

from agents import MinimaxAgent
from domino.game import Game
from domino.player import Player
from domino.tile import Tile
from test_multiplayer_minimax import HiddenTiles


def setup_agent(**kwargs):
    agent = MinimaxAgent(strategy="maxn", time_limit=10, max_nodes=100000, **kwargs)
    agent._deadline = perf_counter() + 10
    agent.last_stats = {"nodes": 0, "cutoffs": 0}
    return agent


def exhaustive(game, agent, depth):
    if depth == 0 or game.round_over:
        return agent._evaluate_vector(game)
    options = []
    for action in agent._actions(game):
        child = deepcopy(game)
        child.apply_action(action)
        options.append(exhaustive(child, agent, depth - 1))
    return max(options, key=lambda values: values[game.current_player_index])


@pytest.mark.parametrize("players,turn", [(3, 0), (3, 1), (3, 2), (4, 0), (4, 3)])
def test_maxn_matches_exhaustive_vector_search(players, turn):
    game = Game()
    game.players = [Player(str(i), [Tile((6, i)), Tile((i, i))]) for i in range(players)]
    game.table.add_first_tile(Tile((6, 6)))
    game.current_player_index = turn
    agent = setup_agent()
    assert agent._search_maxn(game, 4) == exhaustive(game, agent, 4)


def test_opponent_maximizes_own_score_instead_of_minimizing_root(monkeypatch):
    class Node:
        def __init__(self, actor=1, scores=None):
            self.current_player_index = actor
            self.scores = scores
            self.round_over = scores is not None

        def apply_action(self, action):
            self.scores = action
            self.round_over = True

    agent = setup_agent()
    options = [(-10, 1, 0), (5, 8, -1)]
    monkeypatch.setattr(agent, "_actions", lambda game: options)
    monkeypatch.setattr(agent, "_evaluate_vector", lambda game: game.scores)
    monkeypatch.setattr(agent, "_evaluate", lambda game: game.scores[0])
    assert agent._search_maxn(Node(), 1) == (5, 8, -1)
    assert agent._search(Node(), 1, -inf, inf) == -10


@pytest.mark.parametrize("players", [3, 4])
def test_maxn_does_not_read_hidden_tiles_or_modify_state(players):
    game = Game()
    game.start_round(n_players=players, tile_count=5)
    own = game.current_player_index
    for i, player in enumerate(game.players):
        if i != own:
            player.tiles = HiddenTiles(player.tiles)
    game.stock = HiddenTiles(game.stock)
    game.tiles = HiddenTiles(game.tiles)
    history = list(game.public_history)
    hand = list(game.current_player.tiles)
    agent = MinimaxAgent(strategy="maxn", seed=2)
    game.apply_action(agent.choose_action(game))
    assert len(game.public_history) == len(history) + 1
    assert len(game.players[own].tiles) == len(hand) - 1


def test_vector_root_matches_original_evaluation():
    game = Game()
    game.start_round(n_players=4, tile_count=5)
    assert MinimaxAgent._evaluate_vector(game)[0] == MinimaxAgent._evaluate(game)
    game.round_over = True
    for winner in game.players:
        game.winner = winner
        scores = MinimaxAgent._evaluate_vector(game)
        assert scores[game.players.index(winner)] == 10000
        assert scores.count(-10000) == 3


def test_two_players_still_use_minimax_alpha_beta():
    game = Game()
    game.start_round(n_players=2)
    agent = MinimaxAgent(strategy="maxn", seed=1)
    game.apply_action(agent.choose_action(game))
    assert agent.last_stats["strategy"] == "paranoid"


def test_rejects_unknown_strategy():
    with pytest.raises(ValueError):
        MinimaxAgent(strategy="invalid")


def test_maxn_respects_node_budget_and_returns_legal_action():
    game = Game()
    game.start_round(n_players=4, tile_count=5)
    agent = MinimaxAgent(strategy="maxn", seed=0, max_nodes=1)
    action = agent.choose_action(game)
    assert agent.last_stats["nodes"] <= 1
    assert agent.last_stats["samples"] == 0
    game.apply_action(action)


@pytest.mark.parametrize("players,expected", [(2, "paranoid"), (3, "maxn"), (4, "maxn")])
def test_automatic_default_uses_selected_strategy(players, expected):
    game = Game()
    game.start_round(n_players=players, tile_count=5)
    agent = MinimaxAgent(seed=1)
    game.apply_action(agent.choose_action(game))
    assert agent.last_stats["strategy"] == expected
