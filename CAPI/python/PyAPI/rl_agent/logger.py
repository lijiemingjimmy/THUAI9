from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from PyAPI.rl_agent.config import AgentConfig
from PyAPI.rl_agent.observation import OBS_VECTOR_DIM, Observation, observation_to_vector
from PyAPI.rl_agent.reward import RewardResult
from PyAPI.rl_agent.utils import now_ms


class RolloutLogger:
    def __init__(self, cfg: AgentConfig, team_id: int, player_id: int) -> None:
        self.path = Path(cfg.log_path) / f"team{team_id}_player{player_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def write(self, obs: Observation, action_id: int, macro_action: str, action_mask: list[int], success: bool, reward: Optional[RewardResult], extra: Optional[Dict[str, Any]] = None) -> None:
        game_id = self.path.parent.parent.name if self.path.parent.name == "agent_jsonl" else self.path.parent.name
        obs_vec = observation_to_vector(obs, OBS_VECTOR_DIM)
        row: Dict[str, Any] = {
            "game_id": game_id,
            "timestamp_ms": now_ms(),
            "game_tick": obs.frame,
            "game_time": obs.game_time,
            "team_id": obs.team_id,
            "player_id": obs.player_id,
            "kind": obs.kind,
            "observation_summary": obs.to_dict(),
            "obs_vector": obs_vec,
            "obs_schema_version": "stage4_v1",
            "raw_action_id": action_id,
            "macro_action_id": action_id,
            "macro_action": macro_action,
            "macro_action_name": macro_action,
            "action_mask": [bool(x) for x in action_mask],
            "action_success": success,
            "api_success": success,
            "score": obs.team_state.get("score"),
            "computing_power": obs.team_state.get("compute_power"),
            "raw_material": obs.team_state.get("material"),
            "factory_hp": obs.team_state.get("factory_hp"),
            "own_factory_hp": obs.team_state.get("factory_hp"),
            "enemy_factory_hp_min": None,
            "visible_enemies": obs.enemies,
            "enemy_visible_count": len(obs.enemies),
            "delta_score": (obs.team_state.get("score") or 0) - (obs.history.get("last_score") or 0),
            "strategic_state": None,
            "role_assignment": None,
            "role_switch_reason": None,
            "local_fsm_state": None,
            "target_type": None,
            "target_cell": None,
            "target_id": None,
            "goods_type": None,
            "amount_bucket": 0,
            "contract_valid": bool(success),
            "contract_reason": "ok" if success else "unknown",
            "sell_succeeded": macro_action == "SELL_GOODS" and success,
            "load_succeeded": macro_action == "LOAD_GOODS" and success,
            "harvest_started": macro_action == "HARVEST" and success,
            "center_occupied": False,
            "reward": reward.total if reward else 0.0,
            "reward_components": reward.components if reward else {},
            "terminal_result": None,
            "done": False,
            "log_prob": None,
            "value": None,
        }
        if extra:
            row.update(extra)
        if "fsm_state" in row and row.get("local_fsm_state") is None:
            row["local_fsm_state"] = row.get("fsm_state")
        if row.get("target") is not None and row.get("target_cell") is None:
            row["target_cell"] = row.get("target")
        if row.get("failure_reason") and not row.get("contract_reason"):
            row["contract_reason"] = row.get("failure_reason")
        row["contract_valid"] = row.get("contract_reason") in {None, "", "ok", "character_busy", "cooldown_active", "no_production_needed", "factory_busy", "factory_storage_full"}
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
