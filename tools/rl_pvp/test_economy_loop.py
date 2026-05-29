from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str], env: dict[str, str], timeout: int) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=True, timeout=timeout)


def analyze(log_dir: Path, out: Path) -> dict:
    run([sys.executable, "tools/rl_pvp/analyze_rollouts.py", "--log-dir", str(log_dir), "--out", str(out)], os.environ.copy(), 120)
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))


def scenario(name: str, duration: int, out: Path, team0_mode: str, team1_mode: str, profile: str) -> dict:
    log_dir = out / name / "logs"
    result = out / name / "result.json"
    env = os.environ.copy()
    if profile:
        env["THUAI9_RULE_PROFILE"] = profile
    run([sys.executable, "tools/rl_pvp/launch_match.py", "--team-count", "2", "--duration", str(duration), "--team0-mode", team0_mode, "--team1-mode", team1_mode, "--result", str(result), "--log-dir", str(log_dir), "--skip-build", "--skip-proto"], env, duration + 150)
    return analyze(log_dir, out / name / "analysis")


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run real-server economy loop integration scenarios.")
    ap.add_argument("--duration", type=int, default=180)
    ap.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/tests/economy_loop"))
    args = ap.parse_args()
    out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    scenarios = [
        ("scenario_a_economy_car", "rule", "random", "economy_only", 1, 0.10),
        ("scenario_b_economy_center", "rule", "rule", "", 1, 0.15),
        ("scenario_c_rule_vs_random", "rule", "random", "", 1, 0.10),
    ]
    summaries = {}
    for name, m0, m1, profile, min_sell, max_invalid in scenarios:
        try:
            s = scenario(name, args.duration, out, m0, m1, profile)
            summaries[name] = s
            econ = s.get("economy_metrics", {})
            require(econ.get("num_sell_succeeded", 0) >= min_sell, f"{name}: sell_succeeded < {min_sell}: {econ}")
            require(s.get("invalid_action_rate", 1.0) <= max_invalid, f"{name}: invalid_action_rate {s.get('invalid_action_rate')} > {max_invalid}")
        except Exception as exc:
            failures.append(str(exc))
    (out / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
