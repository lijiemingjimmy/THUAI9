from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from parse_results import parse_result_file, summarize_games, write_summary

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch evaluate THUAI9 PvP agents.")
    parser.add_argument("--num-games", type=int, default=5)
    parser.add_argument("--team-count", type=int, default=2, choices=[2, 4])
    parser.add_argument("--candidate-mode", default="rule")
    parser.add_argument("--opponent-mode", default="random")
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/eval/summary.json"))
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-proto", action="store_true")
    args = parser.parse_args()
    out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    results = []
    base_port = args.port
    for idx in range(args.num_games):
        result = REPO_ROOT / "outputs" / "rl_pvp" / "results" / f"eval_{idx:04d}.json"
        log_dir = REPO_ROOT / "outputs" / "rl_pvp" / "logs" / f"eval_{idx:04d}"
        cmd = [
            sys.executable, str(REPO_ROOT / "tools" / "rl_pvp" / "launch_match.py"),
            "--team-count", str(args.team_count), "--duration", str(args.duration), "--port", str(base_port + idx % 50),
            "--team0-mode", args.candidate_mode, "--result", str(result), "--log-dir", str(log_dir),
        ]
        for team in range(1, args.team_count):
            cmd.extend([f"--team{team}-mode", args.opponent_mode])
        if args.skip_build or idx > 0:
            cmd.append("--skip-build")
        if args.skip_proto or idx > 0:
            cmd.append("--skip-proto")
        completed = subprocess.run(cmd, cwd=str(REPO_ROOT), timeout=args.duration + 240)
        row = parse_result_file(result)
        row["returncode"] = completed.returncode
        row["log_dir"] = str(log_dir)
        results.append(row)
    summary = summarize_games(results, "Team 1")
    write_summary(summary, out)
    print(out)
    print(out.with_suffix(".csv"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
