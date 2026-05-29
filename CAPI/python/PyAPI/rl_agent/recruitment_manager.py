from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.action_space import TeamAction
from PyAPI.rl_agent.strategic_fsm import StrategicState
from PyAPI.rl_agent.utils import now_ms


@dataclass
class RecruitDecision:
    action: TeamAction
    character_type: Optional[THUAI9.CharacterType]
    reason: str


class RecruitmentManager:
    def __init__(self, cooldown_ms: int = 1500) -> None:
        self.cooldown_ms = cooldown_ms
        self.last_recruit_ms = -10**12

    def choose(self, api, team_info: THUAI9.Team, profile: str, strategic_state: StrategicState, first_sell_done: bool, max_characters: int) -> RecruitDecision:
        now = now_ms()
        if now - self.last_recruit_ms < self.cooldown_ms:
            return RecruitDecision(TeamAction.SAVE_COMPUTE, None, "cooldown_active")
        chars = [c for c in api.GetCharacters() if c.characterActiveState != THUAI9.CharacterState.Deceased]
        ids = {c.playerID for c in chars}
        if team_info.computePower < 50 or len(chars) >= min(3, max_characters):
            return RecruitDecision(TeamAction.SAVE_COMPUTE, None, "not_ready_or_limit")
        profile = (profile or "balanced").lower()
        if profile == "economy_only":
            if 1 not in ids:
                self.last_recruit_ms = now
                return RecruitDecision(TeamAction.RECRUIT_CAR, THUAI9.CharacterType.AutonomousCar, "economy_only_car")
            return RecruitDecision(TeamAction.SAVE_COMPUTE, None, "economy_only_has_car")
        if 1 not in ids:
            self.last_recruit_ms = now
            return RecruitDecision(TeamAction.RECRUIT_CAR, THUAI9.CharacterType.AutonomousCar, "opening_assign_car_economy")
        if 2 not in ids:
            self.last_recruit_ms = now
            return RecruitDecision(TeamAction.RECRUIT_DRONE, THUAI9.CharacterType.Drone, "opening_assign_drone_center")
        if len(chars) < 3:
            self.last_recruit_ms = now
            if profile in {"defense", "pressure_factory"}:
                return RecruitDecision(TeamAction.RECRUIT_ROBOT, THUAI9.CharacterType.Robot, f"{profile}_third_robot")
            if profile == "center_control":
                return RecruitDecision(TeamAction.RECRUIT_ROBOT, THUAI9.CharacterType.Robot, "center_control_third_robot")
            if not first_sell_done and team_info.score <= 0:
                return RecruitDecision(TeamAction.RECRUIT_CAR, THUAI9.CharacterType.AutonomousCar, "economy_slow_third_car")
            return RecruitDecision(TeamAction.RECRUIT_ROBOT, THUAI9.CharacterType.Robot, "balanced_third_robot")
        return RecruitDecision(TeamAction.SAVE_COMPUTE, None, "three_units_ready")
