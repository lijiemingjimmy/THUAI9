from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from analyze_rollouts import analyze
from parse_results import parse_result_file, write_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


def median(xs):
    return statistics.median(xs) if xs else 0.0


def enrich_result(row: Dict[str, Any], log_dir: Path) -> Dict[str, Any]:
    row["log_dir"] = str(log_dir)
    try:
        summary, actions, comps, warnings = analyze(log_dir)
        row["rollout_summary"] = {k: summary.get(k) for k in ["total_steps", "invalid_action_rate", "idle_action_rate", "action_success_rate", "reward_zero_rate", "last_tick_by_game"]}
        row["economy_metrics"] = summary.get("economy_metrics", {})
        row["invalid_by_reason"] = summary.get("invalid_by_reason", {})
        row["invalid_by_fsm_state"] = summary.get("invalid_by_fsm_state", {})
        row["action_hist"] = actions[:20]
        row["rollout_warnings"] = warnings[:20]
        hp_values = []
        first_score = []
        first_center = []
        for game, teams in summary.get("score_curve", {}).items():
            for team, points in teams.items():
                vals = [p for p in points if (p[1] or 0) > 0]
                if vals:
                    first_score.append(vals[0][0])
        for game, teams in summary.get("factory_hp_curve", {}).items():
            for team, points in teams.items():
                if points:
                    hp_values.append(points[-1][1] or 0)
        for action in actions:
            if action.get("macro_action") == "OCCUPY_CENTER" and action.get("count", 0) > 0:
                first_center.append(0)
        row["mean_final_factory_hp_proxy"] = statistics.mean(hp_values) if hp_values else 0.0
        row["first_score_time_proxy"] = statistics.mean(first_score) if first_score else None
        row["first_center_occupation_time_proxy"] = statistics.mean(first_center) if first_center else None
    except Exception as exc:
        row["rollout_parse_error"] = str(exc)
    return row


def build_summary(results: List[Dict[str, Any]], candidate_team: str = "Team 1") -> Dict[str, Any]:
    scores = [int(r.get("scores", {}).get(candidate_team, 0)) for r in results]
    wins = [r for r in results if r.get("winner") == candidate_team]
    ranks = []
    for r in results:
        ranked = [x[0] for x in r.get("ranked", [])]
        ranks.append((ranked.index(candidate_team) + 1) if candidate_team in ranked else None)
    rank_dist = {str(rank): ranks.count(rank) for rank in sorted(set(x for x in ranks if x is not None))}
    invalid_rates = [r.get("rollout_summary", {}).get("invalid_action_rate") for r in results if r.get("rollout_summary")]
    idle_rates = [r.get("rollout_summary", {}).get("idle_action_rate") for r in results if r.get("rollout_summary")]
    hp = [r.get("mean_final_factory_hp_proxy", 0.0) for r in results]
    first_score = [r.get("first_score_time_proxy") for r in results if r.get("first_score_time_proxy") is not None]
    first_center = [r.get("first_center_occupation_time_proxy") for r in results if r.get("first_center_occupation_time_proxy") is not None]
    crashed = [r for r in results if r.get("crashed") or r.get("returncode", 0) != 0]
    timeouts = [r for r in results if r.get("timeout")]
    economy_totals: Dict[str, float] = {}
    for r in results:
        for key, value in (r.get("economy_metrics") or {}).items():
            if isinstance(value, (int, float)) and value is not None:
                economy_totals[key] = economy_totals.get(key, 0.0) + float(value)
    return {
        "num_games": len(results),
        "candidate_team": candidate_team,
        "mean_score": statistics.mean(scores) if scores else 0.0,
        "std_score": statistics.pstdev(scores) if len(scores) > 1 else 0.0,
        "median_score": median(scores),
        "economy_metrics": economy_totals,
        "win_rate": len(wins) / len(results) if results else 0.0,
        "rank_distribution": rank_dist,
        "mean_final_factory_hp": statistics.mean(hp) if hp else 0.0,
        "factory_kill_rate": sum(1 for x in hp if x <= 0) / len(hp) if hp else 0.0,
        "average_first_score_time": statistics.mean(first_score) if first_score else None,
        "average_first_center_occupation_time": statistics.mean(first_center) if first_center else None,
        "kill_death_proxy": None,
        "invalid_action_rate": statistics.mean(invalid_rates) if invalid_rates else 0.0,
        "idle_action_rate": statistics.mean(idle_rates) if idle_rates else 0.0,
        "crash_rate": len(crashed) / len(results) if results else 0.0,
        "timeout_rate": len(timeouts) / len(results) if results else 0.0,
        "average_game_duration": None,
        "games": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch evaluate THUAI9 PvP agents.")
    parser.add_argument("--num-games", type=int, default=5)
    parser.add_argument("--team-count", type=int, default=2, choices=[2, 4])
    parser.add_argument("--candidate-mode", default="rule")
    parser.add_argument("--candidate-checkpoint", default="")
    parser.add_argument("--opponent-mode", default="random")
    parser.add_argument("--opponent-checkpoint", default="")
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/eval/summary.json"))
    parser.add_argument("--log-dir", type=Path, default=Path("outputs/rl_pvp/logs"))
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-proto", action="store_true")
    args = parser.parse_args()
    out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    base_log = args.log_dir if args.log_dir.is_absolute() else REPO_ROOT / args.log_dir
    results = []
    for idx in range(args.num_games):
        result = REPO_ROOT / "outputs" / "rl_pvp" / "results" / f"{out.stem}_{idx:04d}.json"
        log_dir = base_log / f"{out.stem}_{idx:04d}" if args.num_games > 1 else base_log
        cmd = [sys.executable, str(REPO_ROOT / "tools" / "rl_pvp" / "launch_match.py"), "--team-count", str(args.team_count), "--duration", str(args.duration), "--port", str(args.port + idx % 50), "--team0-mode", args.candidate_mode, "--result", str(result), "--log-dir", str(log_dir)]
        if args.candidate_checkpoint:
            cmd.extend(["--team0-checkpoint", args.candidate_checkpoint])
        for team in range(1, args.team_count):
            cmd.extend([f"--team{team}-mode", args.opponent_mode])
            if args.opponent_checkpoint:
                cmd.extend([f"--team{team}-checkpoint", args.opponent_checkpoint])
        if args.skip_build or idx > 0:
            cmd.append("--skip-build")
        if args.skip_proto or idx > 0:
            cmd.append("--skip-proto")
        timeout = False
        try:
            completed = subprocess.run(cmd, cwd=str(REPO_ROOT), timeout=args.duration + 240)
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            timeout = True
            returncode = 124
        row = parse_result_file(result)
        row["returncode"] = returncode
        row["timeout"] = timeout
        results.append(enrich_result(row, log_dir))
    summary = build_summary(results, "Team 1")
    write_summary(summary, out)
    print(json.dumps({k: v for k, v in summary.items() if k != "games"}, ensure_ascii=False, indent=2))
    print(out)
    print(out.with_suffix(".csv"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
