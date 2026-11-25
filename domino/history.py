"""Eventos públicos da rodada; compras nunca revelam a identidade da peça."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PublicAction:
    player_index: int
    kind: Literal["play", "draw", "pass"]
    endpoints: tuple[int | None, int | None]
    tile: tuple[int, int] | None = None
