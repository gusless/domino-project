import random

import pytest

from agents import GreedyAgent, RandomAgent
from domino.actions import DrawAction, PassAction, PlayAction
from domino.game import Game
from domino.player import Player
from domino.tile import Tile


def configured_game(hands, stock=(), has_stock=False, pull_one=False):
    game = Game()
    game.players = [Player(f"P{i + 1}", [Tile(t) for t in hand])
                    for i, hand in enumerate(hands)]
    game.table.add_first_tile(Tile((6, 6)))
    game.stock = [Tile(t) for t in stock]
    game.has_stock = has_stock
    game.pull_one = pull_one
    return game


def test_deal_conserves_all_tiles_and_selects_highest_double():
    game = Game()
    game.start_round(n_players=2, tile_count=7)
    tiles = [tile for player in game.players for tile in player.tiles] + game.stock
    assert len(tiles) == 28
    assert len({tuple(sorted(tile)) for tile in tiles}) == 28
    prioritized = game.get_generic_prioritized_tiles(
        [tile for player in game.players for tile in player.tiles])
    assert prioritized[0] in game.current_player.tiles


@pytest.mark.parametrize("players,count", [(1, 7), (5, 5), (4, 8), (2, 4)])
def test_invalid_configuration(players, count):
    with pytest.raises(ValueError):
        Game().start_round(n_players=players, tile_count=count)


def test_last_tile_ends_round_and_scores_once():
    game = configured_game([[(6, 1)], [(1, 2)]])
    game.apply_action(PlayAction(0, "right"))
    assert game.round_over

    winner = game.winner
    assert winner is game.players[0]
    assert winner is not None
    assert winner.wins == 1
    with pytest.raises(RuntimeError):
        game.apply_action(PassAction())
    assert winner.wins == 1


@pytest.mark.parametrize("pull_one,drawn,expected", [
    (False, (1, 2), 0), (True, (1, 2), 1), (True, (6, 2), 0)])
def test_draw_turn_policy(pull_one, drawn, expected):
    game = configured_game([[(1, 1)], [(6, 3)]],
                           stock=[drawn], has_stock=True, pull_one=pull_one)
    game.apply_action(DrawAction())
    assert game.current_player_index == expected
    assert len(game.players[0].tiles) == 2
    assert game.draw_result == Tile(drawn)
    assert not game.stock


def test_cannot_draw_or_pass_when_play_is_available():
    game = configured_game([[(6, 1)], [(6, 3)]], stock=[(2, 2)], has_stock=True)
    for action in (DrawAction(), PassAction()):
        with pytest.raises(ValueError):
            game.apply_action(action)
    assert len(game.stock) == 1
    assert game.current_player_index == 0


def test_cannot_pass_when_stock_remains():
    game = configured_game([[(1, 1)], [(6, 3)]], stock=[(2, 2)], has_stock=True)
    with pytest.raises(ValueError):
        game.apply_action(PassAction())


def test_pass_advances_turn():
    game = configured_game([[(1, 1)], [(6, 3)]])
    game.apply_action(PassAction())
    assert game.current_player_index == 1
    assert not game.round_over


@pytest.mark.parametrize("other,expected", [((2, 2), 0), ((0, 2), None)])
def test_locked_round_uses_points_and_detects_tie(other, expected):
    game = configured_game([[(1, 1)], [other]])
    game.apply_action(PassAction())
    assert game.round_over
    assert game.winner is (None if expected is None else game.players[expected])


@pytest.mark.parametrize("action,error", [
    (PlayAction(5, "left"), IndexError),
    (PlayAction(0, "invalid"), ValueError)])
def test_invalid_play_preserves_state(action, error):
    game = configured_game([[(6, 1)], [(6, 3)]])
    with pytest.raises(error):
        game.apply_action(action)
    assert game.players[0].tiles == [Tile((6, 1))]
    assert game.table.get_number_of_tiles() == 1
    assert game.current_player_index == 0


def test_next_round_preserves_score_and_resets_state():
    game = configured_game([[(6, 1)], [(1, 2)]])
    game.apply_action(PlayAction(0, "right"))
    game.start_round(n_players=2, tile_count=7)
    assert game.players[0].wins == 1
    assert not game.round_over
    assert game.winner is None
    assert game.table.get_number_of_tiles() == 0


@pytest.mark.parametrize("has_stock,pull_one", [(False, False), (True, False), (True, True)])
def test_agents_finish_round_without_losing_tiles(has_stock, pull_one):
    state = random.getstate()
    random.seed(42)
    try:
        game = Game()
        game.start_round(n_players=2, tile_count=7, has_stock=has_stock, pull_one=pull_one)
        agents = [RandomAgent(), GreedyAgent()]
        for _ in range(300):
            if game.round_over:
                break
            game.apply_action(agents[game.current_player_index].choose_action(game))
            tiles = ([t for p in game.players for t in p.tiles]
                     + list(game.table.tiles_deque) + game.stock + game.tiles)
            assert len(tiles) == 28
            assert len({tuple(sorted(t)) for t in tiles}) == 28
        assert game.round_over
    finally:
        random.setstate(state)
