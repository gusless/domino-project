"""Comparação reproduzível; a versão sem histórico é somente uma referência.

Execute na raiz: python tools/compare_minimax.py --seeds 30
Não cria um segundo agente no menu nem acessa peças ocultas para decidir.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import random
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import GreedyAgent, MinimaxAgent, RandomAgent
from agents.minimax_agent import Observation
from domino.game import Game


def run(seeds=30, baseline_path=None):
    baseline_type = MinimaxAgent
    if baseline_path:
        spec = importlib.util.spec_from_file_location("agents._comparison_baseline", baseline_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        baseline_type = module.MinimaxAgent

    def choose(agent, game, historical):
        if historical or baseline_path:
            return agent.choose_action(game)
        return agent.choose_observation(replace(Observation.from_game(game), history=()))

    def match(seed, has_stock, seat, historical, opponent_type=None):
        random.seed(seed)
        game = Game()
        game.start_round(n_players=2, tile_count=7, has_stock=has_stock, pull_one=False)
        active = MinimaxAgent(seed=seed + 1000) if historical else baseline_type(seed=seed + 1000)
        opponent = (opponent_type() if opponent_type else baseline_type(seed=seed + 2000))
        agents = [opponent, opponent]
        agents[seat] = active
        durations = []
        zero_samples = 0
        for _ in range(200):
            if game.round_over:
                break
            actor = game.current_player_index
            if actor == seat:
                action = choose(active, game, historical)
                durations.append(active.last_stats["seconds"])
                zero_samples += int(active.last_stats["nodes"] > 0
                                    and active.last_stats["samples"] == 0)
            elif opponent_type:
                action = agents[actor].choose_action(game)
            else:
                action = choose(opponent, game, False)
            game.apply_action(action)
        if not game.round_over:
            raise RuntimeError("Rodada não encerrou em 200 ações")
        outcome = ("draw" if game.winner is None else
                   "win" if game.winner is game.players[seat] else "loss")
        return outcome, durations, zero_samples

    rows = []
    all_times = {"history": [], "baseline": []}
    for opponent_type in (RandomAgent, GreedyAgent):
        for has_stock in (False, True):
            paired = {}
            for historical in (False, True):
                name = "history" if historical else "baseline"
                outcomes = {"win": 0, "loss": 0, "draw": 0}
                times = []
                zero = 0
                for seed in range(seeds):
                    for seat in (0, 1):
                        outcome, elapsed, skipped = match(seed, has_stock, seat, historical, opponent_type)
                        outcomes[outcome] += 1
                        times.extend(elapsed)
                        zero += skipped
                all_times[name].extend(times)
                paired[name] = outcomes
                rows.append(dict(version=name, opponent=opponent_type.__name__,
                                 stock=has_stock, games=seeds * 2, **outcomes,
                                 decisions=len(times), mean_ms=1000 * sum(times) / len(times),
                                 max_ms=1000 * max(times), searches_without_complete_sample=zero))
            print(opponent_type.__name__, "stock", has_stock, paired, flush=True)

    head = {"win": 0, "loss": 0, "draw": 0}
    for has_stock in (False, True):
        for seed in range(seeds):
            for seat in (0, 1):
                outcome, _, _ = match(seed, has_stock, seat, True)
                head[outcome] += 1
    print("Confronto direto (perspectiva com histórico):", head, flush=True)
    return {
        "seeds": seeds, "depth": 3, "samples": 6, "max_nodes": 2500,
        "time_limit_seconds": 0.2,
        "reference": "saved_previous_agent" if baseline_path else "same_agent_without_history",
        "method": "Seeds pareadas, lugares alternados, com e sem monte; 7 peças por jogador.",
        "rows": rows, "head_to_head": head,
        "overall_timing": {name: {"decisions": len(times),
                                   "mean_ms": 1000 * sum(times) / len(times),
                                   "max_ms": 1000 * max(times)}
                           for name, times in all_times.items()},
        "limitations": "Amostra exploratória; resultados não demonstram superioridade estatística. Tempo pode afetar decisões.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--baseline-path", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/minimax_comparison.json"))
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("seeds deve ser positivo")
    started = perf_counter()
    report = run(args.seeds, args.baseline_path)
    report["elapsed_seconds"] = perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Relatório:", args.output, flush=True)
