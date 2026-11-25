"""Benchmark exploratório do Minimax/paranoid individual, com lugares alternados."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import GreedyAgent, MinimaxAgent, RandomAgent
from domino.game import Game


def benchmark(seeds=4):
    rows = []
    for players in (2, 3, 4):
        for stock in (False, True):
            for opponent_type in (RandomAgent, GreedyAgent):
                outcomes = {"win": 0, "loss": 0, "draw": 0}
                timings = []
                incomplete = nodes = cutoffs = 0
                for seed in range(seeds):
                    for seat in range(players):
                        random.seed(seed)
                        game = Game()
                        # Com 4 jogadores, 5 peças deixa monte disponível.
                        game.start_round(n_players=players, tile_count=5, has_stock=stock)
                        agents = [opponent_type() for _ in range(players)]
                        agent = MinimaxAgent(seed=1000 + seed)
                        agents[seat] = agent
                        for _ in range(200):
                            if game.round_over:
                                break
                            actor = game.current_player_index
                            action = agents[actor].choose_action(game)
                            if actor == seat:
                                stats = agent.last_stats
                                timings.append(stats["seconds"] * 1000)
                                nodes += stats["nodes"]
                                cutoffs += stats["cutoffs"]
                                incomplete += int(stats["nodes"] > 0 and stats["samples"] == 0)
                            game.apply_action(action)
                        if not game.round_over:
                            raise RuntimeError("Rodada não encerrou")
                        outcome = ("draw" if game.winner is None else
                                   "win" if game.winner is game.players[seat] else "loss")
                        outcomes[outcome] += 1
                row = dict(players=players, stock=stock, opponent=opponent_type.__name__,
                           games=seeds * players, **outcomes, decisions=len(timings),
                           mean_ms=sum(timings) / len(timings), max_ms=max(timings),
                           nodes=nodes, cutoffs=cutoffs, incomplete_searches=incomplete)
                rows.append(row)
                print(json.dumps(row), flush=True)
    return dict(seeds=seeds, tiles_per_player=5, depth=3, samples=6,
                max_nodes=2500, time_limit=0.2, rows=rows,
                limitations="Amostra exploratória pequena; não comprova superioridade. Adversários não formam equipes reais.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("reports/minimax_multiplayer.json"))
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("seeds deve ser positivo")
    report = benchmark(args.seeds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
