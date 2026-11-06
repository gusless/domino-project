import random

from domino.actions import DrawAction, PassAction, PlayAction
from domino import rules
from domino.game import Game
from domino.player import Player
from domino.table import Table
from domino.tile import Tile

from agents import *

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from controllers.controller import Controller
    

class CLI:
    """Interface de terminal. Não implementa nem altera regras do jogo."""

    @staticmethod
    def ask_yes_no(prompt: str) -> bool:
        while True:
            answer = input(prompt).strip().lower()
            if answer in {"s", "sim", "y", "yes"}:
                return True
            if answer in {"n", "não", "nao", "no", "not"}:
                return False
            print("Digite 's' ou 'n'.")

    def ask_configuration(self) -> tuple[int, int, bool, bool]:
        while True:
            try:
                n_players = int(input("Quantidade de jogadores (2 a 4): "))
                tile_count = int(input("Peças por jogador (mínimo 5): "))
                has_stock = self.ask_yes_no("Terá dorme/compra? (s/n): ")
                pull_one = False
                if has_stock:
                    pull_one = self.ask_yes_no("Limitar a compra a uma peça por vez? (s/n): ")
                if not 2 <= n_players <= 4:
                    raise ValueError("Só são permitidos de 2 a 4 jogadores.")
                if tile_count < 5 or tile_count * n_players > 28:
                    raise ValueError("Quantidade de peças por jogador inválida.")
                return n_players, tile_count, has_stock, pull_one
            except ValueError as error:
                print(f"Configuração inválida: {error}")

    @staticmethod
    def show_table(table: Table) -> None:
        print("\n" + "-" * max(20, table.get_number_of_tiles() * 5))
        print(table)
        print("-" * max(20, table.get_number_of_tiles() * 5))

    @staticmethod
    def show_hand(player: Player, table: Table) -> list[int]:
        playable = rules.get_playable_indices(player, table)
        width = 8

        print(f"\nMão de {player.name}:")
        print("".join(str(tile).center(width) for tile in player.tiles))
        print("".join(
            str(index).center(width) if index in playable else " " * width
            for index in range(len(player.tiles))
        ))
        return playable

    @staticmethod
    def ask_side(tile: Tile, table: Table) -> str:
        if not table.tiles_deque:
            return "right"

        can_left = rules.can_place(tile, table, "left")
        can_right = rules.can_place(tile, table, "right")

        if can_left and not can_right:
            return "left"
        if can_right and not can_left:
            return "right"

        while True:
            answer = input("Jogar à esquerda (L) ou à direita (R)? ").strip().lower()
            if answer in {"l", "left", "e", "esquerda"} and can_left:
                return "left"
            if answer in {"r", "right", "d", "direita"} and can_right:
                return "right"
            print("Escolha um lado válido.")

    def ask_action(self, game: Game):
        player = game.current_player
        playable = self.show_hand(player, game.table)

        if not playable:
            if game.has_stock and game.stock:
                input("Aperte Enter para comprar uma peça...")
                return DrawAction()
            input("Você não pode jogar. Aperte Enter para passar...")
            return PassAction()

        while True:
            try:
                index = int(input("Escolha o índice da peça: "))
                if index not in playable:
                    print("Escolha um índice disponível.")
                    continue
                side = self.ask_side(player.tiles[index], game.table)
                return PlayAction(index, side)
            except ValueError:
                print("Digite um número válido.")


    def show_action(self, action: PlayAction, player: Player):

        tile = player.tiles[action.tile_index]
        print(
            f"Jogou: {tile} no lado "
            + f"{"direito" if action.side == "right" else "esquerdo"}"
        )

    def play_round(self, game: Game, controllers: list[Controller]) -> None:
        while not game.round_over:
            player = game.current_player
            controller = controllers[game.players.index(player)]

            print(f"\nTurno de {player.name}")

            self.show_table(game.table)

            action = controller.choose_action(game)

            if isinstance(action, PlayAction):
                self.show_action(action, player)

            try:
                game.apply_action(action)
            except (ValueError, IndexError, RuntimeError) as error:
                print(f"Jogada inválida: {error}")

        self.show_table(game.table)
        if game.winner is None:
            print("\nEmpate por pontos!")
        elif not game.winner.tiles:
            print(f"\n{game.winner.name} venceu!")
        else:
            print(f"\n{game.winner.name} venceu por pontos!")

        print("\nPlacar da rodada:")
        for position, player in enumerate(game.get_round_ranking(), start=1):
            print(f"{position}º - {player.name}: {player.get_tile_points()} pontos")

        print("\nVitórias:")
        for player in game.get_match_ranking():
            print(f"{player.name}: {player.wins}")


    def ask_agent_vs_agent(self) -> bool:
        mode = input("Digite 0 se você quer IA vs IA: ")
        if mode == "0":
            return True
        return False

    def ask_agent_type(self) -> BaseAgent:
        while True:
            try:
                agent_str = int(input(
                    "\n***Selecioner o tipo do agente***\n" 
                    + "- (0) Escolher aleatoriamente\n" # não seleciona agentes diferentes por enquanto
                    + "- (1) RandomAgent\n"
                    + "- (2) GreedyAgent\n"
                    ))
                
                match agent_str:
                    case 0:
                        return random.choice([
                            RandomAgent(),
                            GreedyAgent(),
                        ])
                    case 1: 
                        return RandomAgent()
                    case 2:
                        return GreedyAgent()
                    case _:
                        raise(ValueError("Escolha um valor válido"))
            except ValueError as error:
                print(error)

