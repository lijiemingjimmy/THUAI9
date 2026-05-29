from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.action_space import CharacterAction
from PyAPI.rl_agent.utils import cell_of, near, now_ms


class CenterFSMState(str, Enum):
    SELECT_CENTER = "SELECT_CENTER"
    MOVE_TO_CENTER = "MOVE_TO_CENTER"
    ALIGN_CENTER = "ALIGN_CENTER"
    START_OCCUPY = "START_OCCUPY"
    WAIT_OCCUPY = "WAIT_OCCUPY"
    DEFEND_CENTER = "DEFEND_CENTER"
    ROTATE_CENTER = "ROTATE_CENTER"
    RECOVER_FROM_FAILURE = "RECOVER_FROM_FAILURE"


@dataclass
class CenterDecision:
    action: CharacterAction
    state: CenterFSMState
    reason: str
    target: Optional[tuple[int, int]] = None


class CenterControlManager:
    def choose_action(self, api, self_info: THUAI9.Character, nav, game_map, local, tracker) -> CenterDecision:
        if self_info.characterType not in (THUAI9.CharacterType.Drone, THUAI9.CharacterType.Robot):
            return CenterDecision(CharacterAction.IDLE, CenterFSMState.RECOVER_FROM_FAILURE, "wrong_character_type")
        origin = cell_of(self_info.x, self_info.y)
        state = CenterFSMState(getattr(local, "center_fsm_state", CenterFSMState.SELECT_CENTER.value))
        if state == CenterFSMState.SELECT_CENTER:
            target = self._select_center(api, nav, game_map, origin, self_info.teamID, local)
            if target is None:
                return CenterDecision(CharacterAction.IDLE, state, "no_reachable_center")
            local.center_target = target
            local.center_fsm_state = CenterFSMState.MOVE_TO_CENTER.value
            return CenterDecision(CharacterAction.GO_CENTER, CenterFSMState.MOVE_TO_CENTER, "selected_center", target)
        target = local.center_target
        if target is None:
            local.center_fsm_state = CenterFSMState.SELECT_CENTER.value
            return CenterDecision(CharacterAction.IDLE, CenterFSMState.SELECT_CENTER, "missing_target")
        center = api.GetComputeCenterState(*target)
        owner = getattr(center, "ownerTeamID", None) if center is not None else None
        if owner == self_info.teamID:
            local.center_occupied = True
            local.center_occupied_time_ms = local.center_occupied_time_ms or now_ms()
            local.center_fsm_state = CenterFSMState.DEFEND_CENTER.value
            return CenterDecision(CharacterAction.IDLE, CenterFSMState.DEFEND_CENTER, "center_owned", target)
        if state in {CenterFSMState.MOVE_TO_CENTER, CenterFSMState.ALIGN_CENTER}:
            if near(origin, target):
                local.center_fsm_state = CenterFSMState.START_OCCUPY.value
                return CenterDecision(CharacterAction.OCCUPY_CENTER, CenterFSMState.START_OCCUPY, "in_range_start_occupy", target)
            return CenterDecision(CharacterAction.GO_CENTER, CenterFSMState.MOVE_TO_CENTER, "move_to_center", target)
        if state == CenterFSMState.START_OCCUPY:
            return CenterDecision(CharacterAction.OCCUPY_CENTER, state, "start_occupy", target)
        if state == CenterFSMState.WAIT_OCCUPY:
            return CenterDecision(CharacterAction.IDLE, state, "occupy_busy_wait", target)
        if state in {CenterFSMState.DEFEND_CENTER, CenterFSMState.ROTATE_CENTER}:
            local.center_target = None
            local.center_fsm_state = CenterFSMState.SELECT_CENTER.value
            return CenterDecision(CharacterAction.IDLE, CenterFSMState.SELECT_CENTER, "rotate_center", None)
        local.center_fsm_state = CenterFSMState.SELECT_CENTER.value
        return CenterDecision(CharacterAction.IDLE, CenterFSMState.SELECT_CENTER, "recover", None)

    def after_action(self, local, action: CharacterAction, success: bool) -> None:
        if action == CharacterAction.OCCUPY_CENTER and success:
            local.center_fsm_state = CenterFSMState.WAIT_OCCUPY.value
        elif not success and action in {CharacterAction.GO_CENTER, CharacterAction.OCCUPY_CENTER}:
            local.center_failure_count += 1
            if local.center_failure_count >= 3 and local.center_target is not None:
                local.center_blacklist.add(local.center_target)
                local.center_target = None
                local.center_fsm_state = CenterFSMState.RECOVER_FROM_FAILURE.value
        elif success:
            local.center_failure_count = 0

    def _select_center(self, api, nav, game_map, origin, team_id: int, local) -> Optional[tuple[int, int]]:
        candidates = []
        for cell in nav.cache.centers:
            if cell in local.center_blacklist:
                continue
            state = api.GetComputeCenterState(*cell)
            if state is not None and state.state == THUAI9.ComputeCenterState.Occupied and state.ownerTeamID == team_id:
                continue
            if not near(origin, cell) and nav.next_step(game_map, origin, cell) is None:
                continue
            candidates.append((abs(origin[0]-cell[0]) + abs(origin[1]-cell[1]), cell))
        return min(candidates)[1] if candidates else None
