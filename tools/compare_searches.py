"""Compara paranoid e Max-n sem mudar hipóteses, avaliação raiz ou orçamento."""

from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import GreedyAgent, MinimaxAgent, RandomAgent
from domino.game import Game


def play(seed, players, tiles, stock, strategies, opponent_type=GreedyAgent):
    random.seed(seed)
    game = Game()
    game.start_round(n_players=players, tile_count=tiles, has_stock=stock)
    agents = [MinimaxAgent(strategy=strategy, seed=seed * 17 + seat)
              if strategy else opponent_type() for seat, strategy in enumerate(strategies)]
    metrics = {name: {"decisions": 0, "seconds": 0.0, "max_seconds": 0.0,
                      "nodes": 0, "incomplete": 0} for name in ("paranoid", "maxn")}
    for _ in range(200):
        if game.round_over:
            break
        seat = game.current_player_index
        action = agents[seat].choose_action(game)
        strategy = strategies[seat]
        if strategy:
            stats = agents[seat].last_stats
            row = metrics[strategy]
            row["decisions"] += 1
            row["seconds"] += stats["seconds"]
            row["max_seconds"] = max(row["max_seconds"], stats["seconds"])
            row["nodes"] += stats["nodes"]
            row["incomplete"] += int(stats["nodes"] > 0 and stats["samples"] == 0)
        game.apply_action(action)
    if not game.round_over:
        raise RuntimeError("Rodada não encerrou em 200 ações")
    winner = None if game.winner is None else game.players.index(game.winner)
    return winner, metrics


def summarize(records):
    result = {}
    for players in (3, 4):
        rows = [r for r in records if r["players"] == players]
        result[str(players)] = {}
        for strategy in ("paranoid", "maxn"):
            own = [r for r in rows if r["strategy"] == strategy]
            metrics = [r["metrics"][strategy] for r in own]
            decisions = sum(m["decisions"] for m in metrics)
            result[str(players)][strategy] = dict(
                games=len(own), wins=sum(r["outcome"] == "win" for r in own),
                draws=sum(r["outcome"] == "draw" for r in own),
                decisions=decisions, mean_ms=1000 * sum(m["seconds"] for m in metrics) / decisions,
                max_ms=1000 * max(m["max_seconds"] for m in metrics),
                incomplete=sum(m["incomplete"] for m in metrics))
        # Intervalo exploratório: reamostragem em blocos de seeds pareadas,
        # preserva a dependência entre lugares e cenários do mesmo sorteio.
        seeds = sorted({r["seed"] for r in rows})
        deltas = []
        for seed in seeds:
            block = [r for r in rows if r["seed"] == seed]
            totals = {name: sum((r["outcome"] == "win") + .5 * (r["outcome"] == "draw")
                                for r in block if r["strategy"] == name)
                      for name in ("paranoid", "maxn")}
            count = sum(r["strategy"] == "maxn" for r in block)
            deltas.append((totals["maxn"] - totals["paranoid"]) / count)
        rng = random.Random(2026)
        boot = sorted(sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(2000))
        result[str(players)]["paired_score_difference_maxn_minus_paranoid"] = dict(
            estimate=sum(deltas) / len(deltas), bootstrap_95_percent=[boot[50], boot[1949]])
    return result


def summarize_head(records):
    result = {}
    for players in (3, 4):
        rows = [r for r in records if r["players"] == players]
        seeds = sorted({r["seed"] for r in rows})
        blocks = []
        for seed in seeds:
            block = [r for r in rows if r["seed"] == seed]
            blocks.append(sum(1 if r["winner"] == "maxn" else
                              -1 if r["winner"] == "paranoid" else 0 for r in block) / len(block))
        rng = random.Random(2026)
        boot = sorted(sum(rng.choice(blocks) for _ in blocks) / len(blocks) for _ in range(2000))
        result[str(players)] = dict(
            games=len(rows), maxn_wins=sum(r["winner"] == "maxn" for r in rows),
            paranoid_wins=sum(r["winner"] == "paranoid" for r in rows),
            draws=sum(r["winner"] is None for r in rows),
            paired_win_difference=sum(blocks) / len(blocks),
            bootstrap_95_percent=[boot[50], boot[1949]])
    return result


def compare(seeds, output):
    records = []
    head = []
    for players in (3, 4):
        for tiles in (5, 7):
            for stock in (False, True):
                for opponent_type in (RandomAgent, GreedyAgent):
                    local = {"paranoid": 0, "maxn": 0}
                    for seed in range(seeds):
                        for seat in range(players):
                            for strategy in ("paranoid", "maxn"):
                                lineup = [None] * players
                                lineup[seat] = strategy
                                winner, metrics = play(seed, players, tiles, stock, lineup, opponent_type)
                                outcome = "draw" if winner is None else "win" if winner == seat else "loss"
                                local[strategy] += int(outcome == "win")
                                records.append(dict(players=players, tiles=tiles, stock=stock,
                                                    opponent=opponent_type.__name__, seed=seed, seat=seat,
                                                    strategy=strategy, outcome=outcome, metrics=metrics))
                    print(players, tiles, stock, opponent_type.__name__, local, flush=True)
    print("Comparação externa concluída; iniciando confronto direto", flush=True)
    for players in (3, 4):
        compositions = (1, 2) if players == 3 else (2,)
        for tiles in (5, 7):
            for stock in (False, True):
                for seed in range(seeds):
                    for count in compositions:
                        for seats in combinations(range(players), count):
                            lineup = ["maxn" if i in seats else "paranoid" for i in range(players)]
                            winner, _ = play(seed, players, tiles, stock, lineup)
                            head.append(dict(players=players, tiles=tiles, stock=stock, seed=seed,
                                             lineup=lineup, winner=None if winner is None else lineup[winner]))
        print("Confronto direto", players,
              {name: sum(r["winner"] == name for r in head if r["players"] == players)
               for name in ("paranoid", "maxn", None)}, flush=True)
    report = dict(seeds=seeds, depth=3, samples=6, max_nodes=2500, time_limit=.2,
                  summary=summarize(records), head_to_head_summary=summarize_head(head),
                  head_to_head=head, records=records,
                  method="Seeds pareadas, todos os lugares, 5/7 peças, com/sem monte; mesma avaliação raiz, hipóteses e limites. Confrontos mistos com composições simétricas.",
                  limitations="Benchmark local; seeds/cenários correlacionados, intervalo exploratório, sem garantia de superioridade universal. Não houve ajuste de parâmetros após os resultados.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path("reports/maxn_vs_paranoid.json"))
    args = parser.parse_args()
    if args.seeds < 2:
        parser.error("Use ao menos duas seeds")
    compare(args.seeds, args.output)
