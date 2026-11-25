from copy import deepcopy
from math import inf
import pickle
import random
from time import perf_counter

import pytest

from agents import MinimaxAgent, GreedyAgent, RandomAgent
from agents.minimax_agent import Observation
from domino.game import Game
from domino.history import PublicAction
from domino.player import Player
from domino.tile import Tile


class HiddenTiles(list):
    def __iter__(self):
        raise AssertionError("Leitura de peças ocultas")

    def __getitem__(self, key):
        raise AssertionError("Leitura de peças ocultas")


@pytest.mark.parametrize("n_players", [2, 3, 4])
def test_all_hidden_hands_and_stock_are_private(n_players):
    game = Game()
    game.start_round(n_players=n_players, tile_count=5)
    own = game.current_player_index
    for index, player in enumerate(game.players):
        if index != own:
            player.tiles = HiddenTiles(player.tiles)
    game.stock = HiddenTiles(game.stock)
    game.tiles = HiddenTiles(game.tiles)
    MinimaxAgent(seed=0).choose_action(game)


@pytest.mark.parametrize("n_players,seat", [(n, i) for n in (2, 3, 4) for i in range(n)])
def test_samples_preserve_counts_rotation_and_all_28_tiles(n_players, seat):
    game = Game()
    game.start_round(n_players=n_players, tile_count=5)
    game.current_player_index = seat
    view = Observation.from_game(game)
    sample = MinimaxAgent(seed=8)._sample_game(view)
    assert len(sample.players) == n_players
    assert sample.current_player_index == 0
    assert sample.players[0].tiles == game.players[seat].tiles
    assert [len(p.tiles) for p in sample.players[1:]] == list(view.opponent_counts)
    tiles = ([t for p in sample.players for t in p.tiles] + sample.stock
             + sample.tiles + list(sample.table.tiles_deque))
    assert len(tiles) == 28
    assert len({tuple(sorted(t)) for t in tiles}) == 28
    before = pickle.dumps(game)
    MinimaxAgent(seed=8).choose_action(game)
    assert pickle.dumps(game) == before


def test_histories_are_separate_and_follow_actual_player_ids():
    view = Observation(((0, 0),), (), (2, 3, 1), 10, True, False, (
        PublicAction(0, "pass", (2, 5)),
        PublicAction(1, "draw", (1, 6)),
        PublicAction(2, "pass", (3, 4)),
        PublicAction(3, "draw", (0, 0)),
    ), own_index=3)
    assert view.hand_constraints(0) == ((frozenset((2, 5)), 0),)
    assert view.hand_constraints(1) == ((frozenset((1, 6)), 1),)
    assert view.hand_constraints(2) == ((frozenset((3, 4)), 0),)
    agent = MinimaxAgent(seed=9)
    sample = agent._sample_game(view)
    for offset, player in enumerate(sample.players[1:], 1):
        actual_index = (view.own_index + offset) % 4
        for numbers, maximum in view.hand_constraints(actual_index):
            assert sum(bool(numbers.intersection(tile)) for tile in player.tiles) <= maximum


def test_joint_assignment_recovers_without_duplicate_or_blocked_hands(monkeypatch):
    agent = MinimaxAgent(seed=0)
    monkeypatch.setattr(agent.rng, "shuffle", lambda _: None)
    hands, rest = agent._distribute([(0, 1), (0, 2)], (1, 1),
                                    [((frozenset((1,)), 0),), ((frozenset((2,)), 0),)])
    assert hands == [[(0, 2)], [(0, 1)]]
    assert rest == []


def exhaustive_paranoid(agent, game, depth):
    if depth == 0 or game.round_over:
        return agent._evaluate(game)
    values = []
    for action in agent._actions(game):
        child = deepcopy(game)
        child.apply_action(action)
        values.append(exhaustive_paranoid(agent, child, depth - 1))
    return (max if game.current_player_index == 0 else min)(values)


@pytest.mark.parametrize("n_players,turn", [(3, 0), (3, 1), (3, 2), (4, 1), (4, 3)])
def test_multiplayer_alpha_beta_matches_unpruned_paranoid(n_players, turn):
    game = Game()
    game.players = [Player(str(i), [Tile((6, i)), Tile((i, i))]) for i in range(n_players)]
    game.table.add_first_tile(Tile((6, 6)))
    game.current_player_index = turn
    agent = MinimaxAgent(max_nodes=100000, time_limit=10)
    agent._deadline = perf_counter() + 10
    agent.last_stats = {"nodes": 0, "cutoffs": 0}
    assert agent._search(game, 4, -inf, inf) == exhaustive_paranoid(agent, game, 4)


@pytest.mark.parametrize("n_players", [3, 4])
def test_any_opponent_win_is_a_loss_and_draw_is_neutral(n_players):
    game = Game()
    game.start_round(n_players=n_players)
    game.round_over = True
    for index in range(n_players):
        game.winner = game.players[index]
        assert MinimaxAgent._evaluate(game) == (10000 if index == 0 else -10000)
    game.winner = None
    assert MinimaxAgent._evaluate(game) == 0


@pytest.mark.parametrize("n_players", [3, 4])
@pytest.mark.parametrize("has_stock,pull_one", [(False, False), (True, False), (True, True)])
def test_multiplayer_full_rounds_and_truthful_constraints(n_players, has_stock, pull_one):
    state = random.getstate()
    try:
        for seed in range(3):
            random.seed(seed)
            game = Game()
            game.start_round(n_players=n_players, tile_count=5, has_stock=has_stock, pull_one=pull_one)
            agents = [MinimaxAgent(seed=seed, samples=2, max_nodes=600), RandomAgent(), GreedyAgent()]
            if n_players == 4:
                agents.append(RandomAgent())
            for _ in range(200):
                if game.round_over:
                    break
                view = Observation.from_game(game)
                for opponent in range(n_players):
                    if opponent != game.current_player_index:
                        assert all(sum(bool(numbers.intersection(t)) for t in game.players[opponent].tiles)
                                   <= limit for numbers, limit in view.hand_constraints(opponent))
                game.apply_action(agents[game.current_player_index].choose_action(game))
                tiles = ([t for p in game.players for t in p.tiles] + game.stock + game.tiles
                         + list(game.table.tiles_deque))
                assert len(tiles) == 28
                assert len({tuple(sorted(t)) for t in tiles}) == 28
            assert game.round_over
    finally:
        random.setstate(state)
