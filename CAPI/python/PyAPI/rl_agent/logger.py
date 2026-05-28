from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from PyAPI.rl_agent.config import AgentConfig
from PyAPI.rl_agent.observation import Observation
from PyAPI.rl_agent.reward import RewardResult
from PyAPI.rl_agent.utils import now_ms


class RolloutLogger:
    def __init__(self, cfg: AgentConfig, team_id: int, player_id: int) -> None:
        self.path = Path(cfg.log_path) / f"team{team_id}_player{player_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def write(self, obs: Observation, action_id: int, macro_action: str, action_mask: list[int], success: bool, reward: Optional[RewardResult], extra: Optional[Dict[str, Any]] = None) -> None:
        row: Dict[str, Any] = {
            "timestamp_ms": now_ms(),
            "game_tick": obs.frame,
            "game_time": obs.game_time,
            "team_id": obs.team_id,
            "player_id": obs.player_id,
            "kind": obs.kind,
            "observation_summary": obs.to_dict(),
            "raw_action_id": action_id,
            "macro_action_name": macro_action,
            "action_mask": action_mask,
            "action_success": success,
            "score": obs.team_state.get("score"),
            "computing_power": obs.team_state.get("compute_power"),
            "raw_material": obs.team_state.get("material"),
            "factory_hp": obs.team_state.get("factory_hp"),
            "visible_enemies": obs.enemies,
            "reward": reward.total if reward else 0.0,
            "reward_components": reward.components if reward else {},
            "terminal_result": None,
        }
        if extra:
            row.update(extra)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
