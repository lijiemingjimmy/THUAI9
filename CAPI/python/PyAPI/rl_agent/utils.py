from __future__ import annotations

import math
import time
from concurrent.futures import Future
from enum import IntEnum
from typing import Any, Dict, Iterable, Optional, Tuple

import PyAPI.structures as THUAI9

Cell = Tuple[int, int]
CELL_SIZE = 1000
INTERACT_RANGE = 1
PASSABLE = {THUAI9.PlaceType.Space, THUAI9.PlaceType.Bush}


def now_ms() -> int:
    return int(time.time() * 1000)


def cell_of(x: int, y: int) -> Cell:
    return x // CELL_SIZE, y // CELL_SIZE


def grid_center(cell: Cell) -> Tuple[int, int]:
    return cell[0] * CELL_SIZE + CELL_SIZE // 2, cell[1] * CELL_SIZE + CELL_SIZE // 2


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def near(a: Cell, b: Cell, radius: int = INTERACT_RANGE) -> bool:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= radius


def angle_to(src_x: int, src_y: int, dst_x: int, dst_y: int) -> float:
    angle = math.atan2(dst_y - src_y, dst_x - src_x)
    return angle + math.tau if angle < 0 else angle


def accepted(future_or_bool: Any, timeout: float = 0.05) -> bool:
    try:
        if isinstance(future_or_bool, Future):
            return bool(future_or_bool.result(timeout=timeout))
        if hasattr(future_or_bool, "result"):
            return bool(future_or_bool.result(timeout=timeout))
        return bool(future_or_bool)
    except Exception:
        return False


def enum_name(value: Any) -> str:
    return getattr(value, "name", str(value))


def enum_value(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def goods_total(goods: Dict[THUAI9.GoodsType, int] | Dict[Any, int]) -> int:
    return sum(int(v) for v in goods.values() if int(v) > 0)


def goods_dict(goods: Dict[Any, int]) -> Dict[str, int]:
    return {enum_name(k): int(v) for k, v in goods.items() if int(v) != 0}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def iter_cells(game_map: list[list[THUAI9.PlaceType]]) -> Iterable[tuple[Cell, THUAI9.PlaceType]]:
    for x, row in enumerate(game_map or []):
        for y, place in enumerate(row):
            yield (x, y), place
