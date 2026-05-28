from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "CAPI" / "python"))
sys.path.insert(0, str(REPO_ROOT / "CAPI" / "python" / "proto"))


def iter_jsonl(root: Path):
    for path in root.rglob("*.jsonl"):
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="PPO skeleton for THUAI9 rollout logs.")
    parser.add_argument("--config", type=Path, default=Path("configs/rl_pvp/ppo.yaml"))
    parser.add_argument("--data", type=Path, default=Path("outputs/rl_pvp/logs"))
    parser.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/checkpoints/ppo_skeleton.pt"))
    args = parser.parse_args()
    rows = list(iter_jsonl(args.data))
    print(f"loaded_steps={len(rows)}")
    print("TODO: featurize observations -> compute GAE -> PPO clipped update -> save checkpoint")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        import torch
        from PyAPI.rl_agent.models import THUAI9PolicyNet

        model = THUAI9PolicyNet(obs_dim=64, action_dim=16)
        torch.save({"model": model.state_dict(), "obs_dim": 64, "note": "skeleton checkpoint"}, args.out)
        print(f"checkpoint={args.out}")
    except Exception as exc:
        print(f"PyTorch unavailable or import failed: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
