from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.action_space import CHARACTER_ACTIONS, TEAM_ACTIONS, character_action_mask, mask_as_list, team_action_mask
from PyAPI.rl_agent.navigation import Navigator
from PyAPI.rl_agent.state_tracker import PlayerLocalState
from PyAPI.rl_agent.utils import cell_of, enum_name, enum_value, goods_dict, goods_total


@dataclass
class Observation:
    player_id: int
    team_id: int
    frame: int
    game_time: int
    kind: str
    self_state: Dict[str, Any] = field(default_factory=dict)
    team_state: Dict[str, Any] = field(default_factory=dict)
    allies: List[Dict[str, Any]] = field(default_factory=list)
    enemies: List[Dict[str, Any]] = field(default_factory=list)
    map_summary: Dict[str, Any] = field(default_factory=dict)
    history: Dict[str, Any] = field(default_factory=dict)
    action_mask: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_observation(api, player_id: int, nav: Navigator, state: PlayerLocalState, is_team: bool) -> Observation:
    frame = safe_call(api.GetFrameCount, 0)
    game_info = safe_call(api.GetGameInfo, THUAI9.GameInfo())
    game_map = safe_call(api.GetFullMap, [])
    nav.update(game_map)
    team_info = api.GetSelfInfo() if is_team else _team_from_gameinfo(game_info, 0)
    if not is_team:
        self_info = api.GetSelfInfo()
        team_id = self_info.teamID if self_info else 0
        team_info = _team_from_gameinfo(game_info, team_id)
    else:
        self_info = None
        team_id = team_info.teamID if team_info else 0
    obs = Observation(player_id=player_id, team_id=team_id, frame=frame, game_time=getattr(game_info, "gameTime", 0), kind="team" if is_team else "character")
    if team_info is not None:
        obs.team_state = _team_dict(team_info)
    if self_info is not None:
        obs.self_state = _character_dict(self_info)
    obs.allies = [_character_dict(c) for c in safe_call(api.GetCharacters, [])]
    obs.enemies = [_character_dict(c) for c in safe_call(api.GetEnemyCharacters, [])[:12]]
    obs.map_summary = {
        "resources": len(nav.cache.resources),
        "compute_centers": len(nav.cache.centers),
        "markets": len(nav.cache.markets),
        "factories": len(nav.cache.factories),
        "size": [len(game_map), len(game_map[0]) if game_map else 0],
    }
    obs.history = {
        "last_action": state.last_macro_action,
        "last_target": list(state.last_target) if state.last_target else None,
        "last_score": state.last_score,
        "last_factory_hp": state.last_factory_hp,
        "last_action_success": state.last_action_success,
        "invalid_actions": state.invalid_actions,
    }
    if is_team and team_info is not None:
        obs.action_mask = mask_as_list(team_action_mask(api, team_info), TEAM_ACTIONS)
    elif self_info is not None:
        obs.action_mask = mask_as_list(character_action_mask(api, self_info, nav, game_map), CHARACTER_ACTIONS)
    return obs


def build_privileged_state(api) -> Dict[str, Any]:
    info = safe_call(api.GetGameInfo, THUAI9.GameInfo())
    return {"game_time": getattr(info, "gameTime", 0), "teams": [_team_dict(t) for t in getattr(info, "teams", [])]}


def _character_dict(ch: THUAI9.Character) -> Dict[str, Any]:
    return {
        "team_id": ch.teamID,
        "player_id": ch.playerID,
        "type": enum_name(ch.characterType),
        "state": enum_name(ch.characterActiveState),
        "cell": list(cell_of(ch.x, ch.y)),
        "x": ch.x,
        "y": ch.y,
        "hp": ch.hp,
        "speed": ch.speed,
        "view_range": ch.viewRange,
        "attack": ch.commonAttack,
        "attack_range": ch.commonAttackRange,
        "load": ch.currentLoad,
        "capacity": ch.carryCapacity,
        "goods_total": goods_total(ch.goodsLoad),
        "goods": goods_dict(ch.goodsLoad),
    }


def _team_dict(team) -> Dict[str, Any]:
    return {
        "team_id": getattr(team, "teamID", 0),
        "score": getattr(team, "score", 0),
        "material": getattr(team, "material", 0),
        "compute_power": getattr(team, "computePower", 0),
        "factory_hp": getattr(team, "factoryHP", 0),
        "tech_levels": dict(getattr(team, "techLevels", {}) or {}),
    }


def _team_from_gameinfo(game_info: THUAI9.GameInfo, team_id: int):
    for team in getattr(game_info, "teams", []):
        if team.teamID == team_id:
            return team
    return None


def safe_call(fn, default):
    try:
        return fn()
    except Exception:
        return default
