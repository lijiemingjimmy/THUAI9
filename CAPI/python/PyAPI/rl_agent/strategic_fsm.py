from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.utils import cell_of, near, now_ms


class StrategicState(str, Enum):
    OPENING = "OPENING"
    ECONOMY_STABILIZE = "ECONOMY_STABILIZE"
    CENTER_CONTROL = "CENTER_CONTROL"
    THIRD_UNIT_TIMING = "THIRD_UNIT_TIMING"
    DEFENSE = "DEFENSE"
    HUNT_ENEMY = "HUNT_ENEMY"
    PRESSURE_FACTORY = "PRESSURE_FACTORY"
    ENDGAME = "ENDGAME"


class RoleAssignment(str, Enum):
    ECONOMY = "ECONOMY"
    CENTER = "CENTER"
    DEFENSE = "DEFENSE"
    SCOUT = "SCOUT"
    HUNT = "HUNT"
    PRESSURE_FACTORY = "PRESSURE_FACTORY"
    RETREAT = "RETREAT"
    IDLE = "IDLE"


@dataclass
class StrategicDecision:
    state: StrategicState
    roles: Dict[int, RoleAssignment]
    reason: str
    enemy_near_factory: bool = False
    own_factory_under_attack: bool = False


class StrategicFSM:
    def __init__(self, min_state_duration_ms: int = 5000, min_role_duration_ms: int = 3000) -> None:
        self.min_state_duration_ms = min_state_duration_ms
        self.min_role_duration_ms = min_role_duration_ms

    def update(self, api, tracker, team_id: int, profile: str) -> StrategicDecision:
        profile = (profile or "balanced").lower()
        now = now_ms()
        game_info = api.GetGameInfo()
        game_time = int(getattr(game_info, "gameTime", 0) or 0)
        chars = [c for c in api.GetCharacters() if c.characterActiveState != THUAI9.CharacterState.Deceased]
        enemies = [e for e in api.GetEnemyCharacters() if e.characterActiveState != THUAI9.CharacterState.Deceased]
        own_factory = _own_factory_cell(api, team_id)
        enemy_near_factory = _enemy_near_cell(enemies, own_factory, radius=4)
        team = _team_from_gameinfo(game_info, team_id)
        score = int(getattr(team, "score", 0) or 0) if team else 0
        compute = int(getattr(team, "computePower", 0) or 0) if team else 0
        if score > 0:
            tracker.first_sell_done = True
        if len(chars) >= 3 and not getattr(tracker, "third_unit_built_time", 0):
            tracker.third_unit_built_time = now
        if enemy_near_factory:
            tracker.enemy_near_factory = True
            tracker.last_enemy_seen_time = now
            if enemies:
                tracker.last_enemy_seen = cell_of(enemies[0].x, enemies[0].y)
        state = StrategicState(str(getattr(tracker, "current_strategic_state", StrategicState.OPENING.value)))
        reason = "keep_state"
        desired = state
        if profile == "economy_only":
            desired, reason = StrategicState.ECONOMY_STABILIZE, "economy_only_profile"
        elif enemy_near_factory or getattr(tracker, "own_factory_under_attack", False):
            desired, reason = StrategicState.DEFENSE, "enemy_near_factory"
        elif game_time > 0 and game_time >= 0.85 * 180000:
            desired, reason = StrategicState.ENDGAME, "endgame_time"
        elif state == StrategicState.OPENING:
            if any(_is_economy(c) for c in chars) or game_time > 12000:
                desired, reason = StrategicState.ECONOMY_STABILIZE, "opening_done"
        elif state == StrategicState.ECONOMY_STABILIZE:
            if tracker.first_sell_done or score > 0 or game_time > 45000:
                desired, reason = StrategicState.CENTER_CONTROL, "first_sell_done"
        elif state == StrategicState.CENTER_CONTROL:
            if len(chars) < 3 and compute >= 50:
                desired, reason = StrategicState.THIRD_UNIT_TIMING, "compute_enough_for_third_unit"
            elif profile in {"pressure_factory", "bc_teacher"} and game_time > 35000:
                desired, reason = StrategicState.PRESSURE_FACTORY, "pressure_profile_midgame"
        elif state == StrategicState.THIRD_UNIT_TIMING:
            if len(chars) >= 3:
                if profile == "defense":
                    desired, reason = StrategicState.DEFENSE, "defense_profile"
                elif profile in {"pressure_factory", "bc_teacher"} and game_time > 35000:
                    desired, reason = StrategicState.PRESSURE_FACTORY, "third_unit_built_pressure"
                else:
                    desired, reason = StrategicState.CENTER_CONTROL, "third_unit_built"
        elif state == StrategicState.DEFENSE:
            if not enemy_near_factory and now - int(getattr(tracker, "last_enemy_seen_time", 0) or 0) > 7000:
                desired, reason = StrategicState.CENTER_CONTROL, "defense_clear"
        elif state == StrategicState.PRESSURE_FACTORY:
            if profile == "balanced" and score <= 0 and game_time < 60000:
                desired, reason = StrategicState.CENTER_CONTROL, "pressure_not_ready"
        if desired != state and now - int(getattr(tracker, "last_strategic_state_switch_ms", 0) or 0) >= self.min_state_duration_ms:
            tracker.current_strategic_state = desired.value
            tracker.last_strategic_state_switch_ms = now
            tracker.role_switch_reason = reason
            state = desired
        roles = self.assign_roles(chars, state, profile, enemy_near_factory)
        self._commit_roles(tracker, roles, reason)
        return StrategicDecision(state=state, roles=roles, reason=reason, enemy_near_factory=enemy_near_factory)

    def assign_roles(self, chars: Iterable[THUAI9.Character], state: StrategicState, profile: str, enemy_near_factory: bool) -> Dict[int, RoleAssignment]:
        roles: Dict[int, RoleAssignment] = {}
        for ch in chars:
            if ch.hp > 0 and ch.hp < 35:
                roles[ch.playerID] = RoleAssignment.RETREAT
            elif _is_economy(ch):
                roles[ch.playerID] = RoleAssignment.ECONOMY
            elif profile == "economy_only":
                roles[ch.playerID] = RoleAssignment.IDLE
            elif state == StrategicState.DEFENSE or profile == "defense" or enemy_near_factory:
                roles[ch.playerID] = RoleAssignment.DEFENSE
            elif state == StrategicState.PRESSURE_FACTORY or profile == "pressure_factory":
                roles[ch.playerID] = RoleAssignment.PRESSURE_FACTORY
            elif state == StrategicState.HUNT_ENEMY:
                roles[ch.playerID] = RoleAssignment.HUNT
            elif profile in {"center_control", "balanced", "bc_teacher"}:
                roles[ch.playerID] = RoleAssignment.CENTER
            else:
                roles[ch.playerID] = RoleAssignment.SCOUT
        return roles

    def _commit_roles(self, tracker, roles: Dict[int, RoleAssignment], reason: str) -> None:
        now = now_ms()
        for player_id, role in roles.items():
            old = tracker.role_assignment_by_player.get(player_id)
            last = tracker.last_role_switch_time.get(player_id, 0)
            if old is None or old == role.value or now - last >= self.min_role_duration_ms:
                tracker.role_assignment_by_player[player_id] = role.value
                tracker.last_role_switch_time[player_id] = now
                tracker.role_switch_reason = reason


def _is_economy(ch: THUAI9.Character) -> bool:
    return ch.playerID == 1 or ch.characterType == THUAI9.CharacterType.AutonomousCar


def _team_from_gameinfo(game_info, team_id: int):
    for team in getattr(game_info, "teams", []) or []:
        if getattr(team, "teamID", None) == team_id:
            return team
    return None


def _own_factory_cell(api, team_id: int) -> Optional[tuple[int, int]]:
    for x, row in enumerate(api.GetFullMap() or []):
        for y, place in enumerate(row):
            if place == THUAI9.PlaceType.Factory:
                fac = api.GetFactoryState(x, y)
                if fac is not None and fac.teamID == team_id:
                    return (x, y)
    return None


def _enemy_near_cell(enemies, cell: Optional[tuple[int, int]], radius: int) -> bool:
    if cell is None:
        return False
    return any(near(cell_of(e.x, e.y), cell, radius) for e in enemies)
