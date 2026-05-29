from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def sample_opponent(pool: Dict[str, float]) -> str:
    names = list(pool) or ["rule"]
    weights = [float(pool[n]) for n in names]
    return random.choices(names, weights=weights, k=1)[0]


def mode_for(name: str) -> str:
    if name in {"rule", "random"}:
        return name
    return "policy"


def run(cmd: list[str], timeout: int) -> int:
    print(" ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=str(REPO_ROOT), timeout=timeout).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal THUAI9 self-play/league loop.")
    parser.add_argument("--config", type=Path, default=Path("configs/rl_pvp/mappo.yaml"))
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--rollout-games", type=int, default=2)
    parser.add_argument("--candidate", type=Path, default=Path("outputs/rl_pvp/checkpoints/mappo/latest.pt"))
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-proto", action="store_true")
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    pool = cfg.get("opponent_pool") or {"rule": 0.4, "random": 0.1, "latest": 0.3, "historical": 0.2}
    league_root = REPO_ROOT / "outputs" / "rl_pvp" / "league"
    league_root.mkdir(parents=True, exist_ok=True)
    latest = args.candidate if args.candidate.is_absolute() else REPO_ROOT / args.candidate
    summary_path = league_root / "league_summary.jsonl"
    for r in range(args.rounds):
        round_dir = league_root / f"round_{r:03d}"
        logs = round_dir / "logs"; results = round_dir / "results"; round_dir.mkdir(parents=True, exist_ok=True)
        opp = sample_opponent(pool)
        opp_mode = mode_for(opp)
        opp_ckpt = str(latest) if opp in {"latest", "historical"} and latest.exists() else ""
        cand_mode = "policy" if latest.exists() else "rule"
        eval_cmd = [sys.executable, str(REPO_ROOT / "tools" / "rl_pvp" / "evaluate.py"), "--num-games", str(args.rollout_games), "--team-count", "2", "--candidate-mode", cand_mode, "--opponent-mode", opp_mode, "--duration", str(args.duration), "--port", str(args.port + r * 60), "--out", str(round_dir / "rollout_summary.json"), "--log-dir", str(logs)]
        if latest.exists():
            eval_cmd.extend(["--candidate-checkpoint", str(latest)])
        if opp_ckpt:
            eval_cmd.extend(["--opponent-checkpoint", opp_ckpt])
        if args.skip_build or r > 0:
            eval_cmd.append("--skip-build")
        if args.skip_proto or r > 0:
            eval_cmd.append("--skip-proto")
        rc_eval = run(eval_cmd, args.duration * args.rollout_games + 600)
        ckpt = round_dir / "checkpoint.pt"
        train_cmd = [sys.executable, str(REPO_ROOT / "tools" / "rl_pvp" / "train_mappo.py"), "--config", str(args.config), "--data", str(logs), "--out", str(ckpt)]
        rc_train = run(train_cmd, 600)
        if ckpt.exists():
            latest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ckpt, latest)
        heldout_cmd = [sys.executable, str(REPO_ROOT / "tools" / "rl_pvp" / "evaluate.py"), "--num-games", "1", "--team-count", "2", "--candidate-mode", "policy" if latest.exists() else "rule", "--candidate-checkpoint", str(latest), "--opponent-mode", "rule", "--duration", str(args.duration), "--port", str(args.port + r * 60 + 40), "--out", str(round_dir / "eval_summary.json"), "--log-dir", str(round_dir / "eval_logs"), "--skip-build", "--skip-proto"]
        rc_heldout = run(heldout_cmd, args.duration + 360)
        row = {"round": r, "opponent": opp, "candidate_mode": cand_mode, "rollout_summary": str(round_dir / "rollout_summary.json"), "eval_summary": str(round_dir / "eval_summary.json"), "checkpoint": str(ckpt), "returncodes": {"rollout": rc_eval, "train": rc_train, "heldout": rc_heldout}}
        with summary_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
