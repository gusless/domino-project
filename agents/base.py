from abc import ABC, abstractmethod
import time

from domino import rules
from domino.game import Game
from domino.tile import Tile
from domino.table import Table
from domino.actions import *

class BaseAgent(ABC):

    def choose_action(self, game: Game) -> Action:
        table = game.table
        player = game.current_player

        playable = rules.get_playable_indices(player, table)

        #time.sleep(1)

        if not playable:
            if game.has_stock and game.stock:
                return DrawAction()
            return PassAction()
        
        return self.choose_play(game, playable)


    @abstractmethod
    def choose_play(self, game: Game, playable: list[int]) -> Action:
        pass


    def choose_side(self, tile: Tile, table: Table) -> str:
        
        if not table.tiles_deque:
            return "right"

        can_left = rules.can_place(tile, table, "left")
        can_right = rules.can_place(tile, table, "right")

        if can_left and not can_right:
            return "left"
        if can_right and not can_left:
            return "right"
        
        return self.select_side(tile, table)

    
    @abstractmethod
    def select_side(self, tile: Tile, table: Table) -> str:
        pass