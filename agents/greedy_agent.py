from agents.base import BaseAgent
import random

import random
from agents.base import BaseAgent
from domino.actions import PlayAction

class GreedyAgent(BaseAgent):
    def choose_play(self, game, playable: list[int]) -> PlayAction:
        """
        Recebe a lista de índices (playable) e escolhe a pedra com a maior soma.
        """
        player = game.current_player
        mao_do_jogador = player.tiles

        best_idx = max(playable, key=lambda idx: sum(mao_do_jogador[idx]))
        best_tile = mao_do_jogador[best_idx]

        side = self.choose_side(best_tile, game.table)
        
        return PlayAction(tile_index=best_idx, side=side) 

    def select_side(self, tile, table) -> str:
        """
        Se a pedra puder jogar de ambos os lados (ex: bucha ou pontas iguais), 
        escolhe aleatoriamente para não ficar previsível.
        """
        return random.choice(["left", "right"])