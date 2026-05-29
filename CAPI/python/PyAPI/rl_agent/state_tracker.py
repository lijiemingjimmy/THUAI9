from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

Cell = Tuple[int, int]

class EconomyState(str, Enum):
    SELECT_RESOURCE = "SELECT_RESOURCE"
    MOVE_TO_RESOURCE = "MOVE_TO_RESOURCE"
    ALIGN_RESOURCE = "ALIGN_RESOURCE"
    START_HARVEST = "START_HARVEST"
    WAIT_HARVEST = "WAIT_HARVEST"
    RETURN_FACTORY = "RETURN_FACTORY"
    ALIGN_FACTORY = "ALIGN_FACTORY"
    WAIT_PRODUCTION = "WAIT_PRODUCTION"
    LOAD_GOODS = "LOAD_GOODS"
    SELECT_MARKET = "SELECT_MARKET"
    MOVE_TO_MARKET = "MOVE_TO_MARKET"
    ALIGN_MARKET = "ALIGN_MARKET"
    SELL_GOODS = "SELL_GOODS"
    RECOVER_FROM_FAILURE = "RECOVER_FROM_FAILURE"



@dataclass
class PlayerLocalState:
    last_decision_ms: int = -10**12
    last_frame: int = -1
    last_score: int = 0
    last_compute_power: int = 0
    last_material: int = 0
    last_factory_hp: int = 0
    last_inventory_value: int = 0
    last_hp: int = 0
    last_target: Optional[Cell] = None
    last_macro_action: str = "idle"
    last_action_success: bool = True
    invalid_actions: int = 0
    visible_enemy_hp: Dict[tuple[int, int], int] = field(default_factory=dict)
    current_macro_action: Optional[str] = None
    current_target: Optional[Cell] = None
    role: str = "unknown"
    failure_count: int = 0
    last_cell: Optional[Cell] = None
    stuck_count: int = 0
    economy_state: EconomyState = EconomyState.SELECT_RESOURCE
    economy_target_resource: Optional[Cell] = None
    economy_target_factory: Optional[Cell] = None
    economy_target_market: Optional[Cell] = None
    blocked_economy_targets: set[Cell] = field(default_factory=set)
    target_goods: str = "Toys"
    state_enter_ms: int = 0
    material_at_harvest_start: int = 0
    score_at_sell_start: int = 0
    loop_count: int = 0


class StateTracker:
    def __init__(self) -> None:
        self.players: Dict[int, PlayerLocalState] = {}
        self.assignments: Dict[int, Cell] = {}
        self.market_cursor: int = 0
        self.tech_cursor: int = 0

    def player(self, player_id: int) -> PlayerLocalState:
        return self.players.setdefault(player_id, PlayerLocalState())

    def clear_assignment(self, player_id: int) -> None:
        self.assignments.pop(player_id, None)

    def assign(self, player_id: int, target: Optional[Cell]) -> None:
        if target is not None:
            self.assignments[player_id] = target

    def assigned_targets(self) -> set[Cell]:
        return set(self.assignments.values())


GLOBAL_TRACKER = StateTracker()
