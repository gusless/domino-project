from controllers import AgentController, HumanController
from domino.actions import PlayAction
from domino.player import Player
from domino.tile import Tile
from interfaces.cli import CLI


def test_cli_imports_with_controllers_and_displays_action(capsys):
    assert AgentController is not None
    assert HumanController is not None
    CLI().show_action(PlayAction(0, "right"), Player("P1", [Tile((6, 1))]))
    assert "direito" in capsys.readouterr().out
