from copy import deepcopy
import random

import pytest

from agents import MinimaxAgent, RandomAgent
from agents.minimax_agent import Observation
from domino.actions import DrawAction, PassAction, PlayAction
from domino.game import Game
from domino.history import PublicAction
from domino.player import Player
from domino.tile import Tile


def observation(history, count=3):
    return Observation(((6, 6),), ((2, 5),), (count,), 4, True, False,
                       tuple(history), 0)


def test_pass_forbids_both_endpoints():
    view = observation([PublicAction(1, "pass", (2, 5))])
    assert view.hand_constraints() == ((frozenset((2, 5)), 0),)
    agent = MinimaxAgent(seed=3)
    for _ in range(30):
        sample = agent._sample_game(view)
        assert all(not {2, 5}.intersection(tile) for tile in sample.players[1].tiles)


def test_draw_allows_one_matching_piece_instead_of_permanent_ban():
    view = observation([PublicAction(1, "draw", (2, 5))])
    assert view.hand_constraints() == ((frozenset((2, 5)), 1),)
    agent = MinimaxAgent(seed=5)
    counts = [sum(bool({2, 5}.intersection(tile))
                  for tile in agent._sample_game(view).players[1].tiles)
              for _ in range(30)]
    assert max(counts) == 1


def test_later_play_consumes_matching_draw_but_keeps_other_numbers_possible():
    view = observation([
        PublicAction(1, "draw", (2, 5)),
        PublicAction(0, "play", (2, 5), (2, 4)),
        PublicAction(1, "play", (4, 5), (4, 5)),
    ])
    assert view.hand_constraints() == ((frozenset((2, 5)), 0),)


def test_later_draw_relaxes_old_absence():
    view = observation([
        PublicAction(1, "pass", (2, 5)),
        PublicAction(1, "draw", (4, 6)),
    ])
    constraints = dict(view.hand_constraints())
    assert constraints[frozenset((2, 5))] == 1
    assert constraints[frozenset((4, 6))] == 1


def test_own_events_are_not_mistaken_for_opponent_evidence():
    view = observation([PublicAction(0, "pass", (2, 5))])
    assert view.hand_constraints() == ()


def test_sampling_deadline_returns_legal_reserve_instead_of_invalid_hypothesis():
    game = Game()
    game.start_round(n_players=2)
    game.public_history = [PublicAction(1 - game.current_player_index, "pass", (2, 5))]
    agent = MinimaxAgent(time_limit=1e-12, seed=0)
    action = agent.choose_action(game)
    assert agent.last_stats["samples"] == 0
    game.apply_action(action)


def test_perspective_of_second_player():
    view = Observation(((6, 6),), ((2, 5),), (3,), 4, True, False,
                       (PublicAction(0, "pass", (2, 5)),), 1)
    assert view.hand_constraints() == ((frozenset((2, 5)), 0),)


def test_history_only_records_successful_public_actions_and_resets():
    game = Game()
    game.players = [Player("P1", [Tile((1, 1))]), Player("P2", [Tile((6, 3))])]
    game.table.add_first_tile(Tile((6, 6)))
    game.has_stock = True
    game.stock = [Tile((0, 0))]
    with pytest.raises(ValueError):
        game.apply_action(PassAction())
    assert game.public_history == []
    game.apply_action(DrawAction())
    assert game.public_history == [PublicAction(0, "draw", (6, 6))]
    assert game.public_history[0].tile is None
    game.apply_action(PassAction())
    game.apply_action(PlayAction(0, "right"))
    assert game.public_history[-1].tile == (6, 3)
    game.start_round(n_players=2)
    assert game.public_history == []


@pytest.mark.parametrize("has_stock,pull_one", [(False, False), (True, False), (True, True)])
def test_real_hands_always_satisfy_deductions_in_complete_rounds(has_stock, pull_one):
    state = random.getstate()
    try:
        for seed in range(12):
            random.seed(seed)
            game = Game()
            game.start_round(n_players=2, has_stock=has_stock, pull_one=pull_one)
            agent = RandomAgent()
            for _ in range(200):
                if game.round_over:
                    break
                view = Observation.from_game(game)
                actual = game.players[1 - game.current_player_index].tiles
                assert all(sum(bool(numbers.intersection(tile)) for tile in actual) <= limit
                           for numbers, limit in view.hand_constraints())
                # Também valida amostragem e privacidade com histórico real.
                snapshot = deepcopy(game)
                sampler = MinimaxAgent(seed=seed)
                sample = sampler._sample_game(view)
                assert all(sum(bool(numbers.intersection(tile))
                               for tile in sample.players[1].tiles) <= limit
                           for numbers, limit in view.hand_constraints())
                assert game.public_history == snapshot.public_history
                game.apply_action(agent.choose_action(game))
            assert game.round_over
    finally:
        random.setstate(state)
