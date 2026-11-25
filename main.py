from domino.game import Game
from interfaces.cli import CLI
from controllers import *
from agents import *


def main() -> None:
    cli = CLI()
    game = Game()

    n_players, tile_count, has_stock, pull_one = cli.ask_configuration()

    # A CLI escolhe a estratégia; cada bot recebe um objeto próprio.
    agent_type = type(cli.ask_agent_type(n_players))

    controllers: list[Controller]

    if cli.ask_agent_vs_agent():
        controllers = [AgentController(agent_type()) for _ in range(n_players)]
    else:
        controllers = [
            HumanController(cli),
            *(AgentController(agent_type()) for _ in range(n_players - 1))
        ]

    while True:
        game.start_round(
            n_players=n_players,
            tile_count=tile_count,
            has_stock=has_stock,
            pull_one=pull_one,
            #controllers=controllers
        )

        cli.play_round(game, controllers)

        if not cli.ask_yes_no("\nDeseja jogar outra rodada? (s/n): "):
            break


if __name__ == "__main__":
    main()
