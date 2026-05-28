from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.config import AgentConfig
from PyAPI.rl_agent.observation import Observation
from PyAPI.rl_agent.state_tracker import PlayerLocalState
from PyAPI.rl_agent.utils import clamp, goods_total

GOODS_VALUE = {
    THUAI9.GoodsType.Semiconductor: 10,
    THUAI9.GoodsType.Medicine: 5,
    THUAI9.GoodsType.Clothes: 4,
    THUAI9.GoodsType.Toys: 2,
    THUAI9.GoodsType.Food: 1,
}


@dataclass
class RewardResult:
    total: float
    components: Dict[str, float] = field(default_factory=dict)


def inventory_value(self_info: Optional[THUAI9.Character]) -> int:
    if self_info is None:
        return 0
    return sum(GOODS_VALUE.get(k, 1) * int(v) for k, v in self_info.goodsLoad.items())


def compute_reward(api, obs: Observation, state: PlayerLocalState, cfg: AgentConfig, action_success: bool, terminal: bool = False) -> RewardResult:
    weights = cfg.reward_weights
    team = obs.team_state
    score = int(team.get("score", 0))
    compute = int(team.get("compute_power", 0))
    material = int(team.get("material", 0))
    factory_hp = int(team.get("factory_hp", 0))
    inv = 0
    if obs.self_state:
        inv = int(obs.self_state.get("goods_total", 0))
    components = {
        "delta_score": (score - state.last_score) * weights.get("delta_score", 0.0),
        "delta_compute_power": (compute - state.last_compute_power) * weights.get("delta_compute_power", 0.0),
        "delta_inventory_value": (inv - state.last_inventory_value) * weights.get("delta_inventory_value", 0.0),
        "own_factory_damage_penalty": max(0, state.last_factory_hp - factory_hp) * weights.get("own_factory_damage_penalty", 0.0),
        "invalid_action_penalty": (0.0 if action_success else weights.get("invalid_action_penalty", 0.0)),
        "idle_penalty": weights.get("idle_penalty", 0.0) if state.last_macro_action.lower().endswith("idle") else 0.0,
    }
    if terminal:
        teams = getattr(api.GetGameInfo(), "teams", [])
        ranked = sorted(teams, key=lambda t: t.score, reverse=True)
        if ranked and ranked[0].teamID == obs.team_id:
            components["terminal_win_bonus"] = weights.get("terminal_win_bonus", 0.0)
        for rank, t in enumerate(ranked):
            if t.teamID == obs.team_id:
                components["terminal_rank_bonus"] = weights.get("terminal_rank_bonus", 0.0) / max(1, rank + 1)
                break
    total = clamp(sum(components.values()), -50.0, 50.0)
    state.last_score = score
    state.last_compute_power = compute
    state.last_material = material
    state.last_factory_hp = factory_hp
    state.last_inventory_value = inv
    return RewardResult(total=total, components=components)
