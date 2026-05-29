from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Behavior cloning placeholder for Stage 4 warm start.")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/checkpoints/bc/latest.pt"))
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    print("Stage 3 keeps BC as a placeholder: collect stable rule/economy_debug (obs, action, mask) first, then train BC in Stage 4.")
    print(f"data={args.data}")
    print(f"out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
