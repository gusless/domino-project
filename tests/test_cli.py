from controllers import AgentController, HumanController
from domino.actions import PlayAction
from domino.player import Player
from domino.tile import Tile
from interfaces.cli import CLI
from agents import RandomAgent
from domino.game import Game


def test_cli_imports_with_controllers_and_displays_action(capsys):
    assert AgentController is not None
    assert HumanController is not None
    CLI().show_action(PlayAction(0, "right"), Player("P1", [Tile((6, 1))]))
    assert "direito" in capsys.readouterr().out


def test_round_reports_draw_and_pass_without_revealing_drawn_tile(capsys):
    game = Game()
    game.players = [Player("P1", [Tile((1, 1))]),
                    Player("P2", [Tile((6, 3))])]
    game.table.add_first_tile(Tile((6, 6)))
    game.has_stock = True
    game.stock = [Tile((0, 0))]
    controllers = [AgentController(RandomAgent()), AgentController(RandomAgent())]

    CLI().play_round(game, controllers)

    output = capsys.readouterr().out
    assert "P1 comprou uma peça." in output
    assert "P1 passou a vez." in output
    assert "[0|0]" not in output
    assert "Jogada inválida" not in output
    assert game.round_over
