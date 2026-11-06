from agents.base import BaseAgent
import random

from agents.base import BaseAgent
from domino.actions import PlayAction
from domino import rules

class GreedyAgent(BaseAgent):
    def choose_play(self, game, playable: list[int]) -> PlayAction:
        """
        Recebe a lista de índices (playable) e escolhe a peça com a maior prioridade:
        primeiro os doubles e depois as maiores somas.
        """
        player = game.current_player

        playable_tiles = [
            (idx, tiles) 
            for idx, tiles in enumerate(player.tiles) 
            if idx in playable
        ]

        priority_tile = game.get_generic_prioritized_tiles(
            [tile for _, tile in playable_tiles]
        )[0]

        tile_idx = next(
            idx for idx, tile in playable_tiles
            if tile == priority_tile
        )

        side = self.choose_side(priority_tile, game.table)
        
        return PlayAction(tile_index=tile_idx, side=side) 

    def select_side(self, tile, table) -> str:
        """
        Se a pedra puder jogar de ambos os lados (ex: bucha ou pontas iguais), 
        escolhe aleatoriamente para não ficar previsível.
        """
        return random.choice(["left", "right"])