from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

CELL_SIZE = 1000


def world_to_cell(x: int, y: int) -> tuple[int, int]:
    return x // CELL_SIZE, y // CELL_SIZE


def cell_to_world_center(x: int, y: int) -> tuple[int, int]:
    return x * CELL_SIZE + CELL_SIZE // 2, y * CELL_SIZE + CELL_SIZE // 2


def angle(src: tuple[int, int], dst: tuple[int, int]) -> float:
    a = math.atan2(dst[1] - src[1], dst[0] - src[0])
    return a + math.tau if a < 0 else a


def main() -> int:
    ap = argparse.ArgumentParser(description="Print coordinate/cell/angle diagnostics from a rollout JSONL row.")
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--line", type=int, default=-1)
    ap.add_argument("--target-cell", nargs=2, type=int, default=None)
    args = ap.parse_args()
    rows = [json.loads(x) for x in args.log.read_text(encoding="utf-8").splitlines() if x.strip()]
    row = rows[args.line]
    self_state: dict[str, Any] = (row.get("observation_summary") or {}).get("self_state") or {}
    x, y = int(self_state.get("x", 0)), int(self_state.get("y", 0))
    cell = world_to_cell(x, y)
    target = tuple(args.target_cell) if args.target_cell else tuple(row.get("target") or cell)
    center = cell_to_world_center(int(target[0]), int(target[1]))
    print(json.dumps({
        "path": str(args.log), "line": args.line, "player_id": row.get("player_id"),
        "world": [x, y], "cell": list(cell), "target_cell": list(target),
        "target_world_center": list(center), "distance": math.hypot(center[0] - x, center[1] - y),
        "angle": angle((x, y), center), "macro_action": row.get("macro_action_name"),
        "fsm_state": row.get("fsm_state"), "success": row.get("action_success"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
