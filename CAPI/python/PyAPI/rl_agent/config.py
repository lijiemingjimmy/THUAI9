from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass
class AgentConfig:
    agent_mode: str = "rule"
    decision_interval_ms: int = 300
    move_time_ms: int = 220
    log_path: Path = REPO_ROOT / "outputs" / "rl_pvp" / "logs"
    checkpoint_path: Path = REPO_ROOT / "outputs" / "rl_pvp" / "checkpoints" / "policy.pt"
    team_id: int = 0
    server_port: int = 8888
    team_count: int = 2
    game_duration: int = 120
    max_characters: int = 6
    map_settings: Dict[str, Any] = field(default_factory=dict)
    reward_weights: Dict[str, float] = field(default_factory=lambda: {
        "delta_score": 0.02,
        "delta_inventory_value": 0.03,
        "delta_compute_power": 0.05,
        "center_occupied_bonus": 1.0,
        "enemy_hp_damage": 0.03,
        "enemy_factory_damage": 0.08,
        "own_factory_damage_penalty": -0.12,
        "kill_bonus": 5.0,
        "death_penalty": -5.0,
        "invalid_action_penalty": -0.4,
        "idle_penalty": -0.01,
        "distance_progress_reward": 0.03,
        "terminal_win_bonus": 25.0,
        "terminal_rank_bonus": 8.0,
    })
    macro_actions: List[str] = field(default_factory=list)
    rule_profile: str = "balanced"
    min_role_duration_ms: int = 3000
    min_strategic_state_duration_ms: int = 5000


def _load_yaml_or_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
    except Exception:
        return _tiny_yaml(text)
    data = yaml.safe_load(text) or {}
    return data if isinstance(data, dict) else {}


def _tiny_yaml(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    stack: List[tuple[int, Dict[str, Any]]] = [(-1, data)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: Dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _coerce(value)
    return data


def _coerce(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def load_config(path: str | Path | None = None) -> AgentConfig:
    raw: Dict[str, Any] = {}
    raw_path = str(path) if path is not None else os.getenv("THUAI9_AGENT_CONFIG", "")
    if raw_path:
        config_path = Path(raw_path)
        raw.update(_load_yaml_or_json(config_path if config_path.is_absolute() else REPO_ROOT / config_path))
    cfg = AgentConfig()
    for key, value in raw.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    if "reward_weights" in raw and isinstance(raw["reward_weights"], dict):
        cfg.reward_weights.update({str(k): float(v) for k, v in raw["reward_weights"].items()})
    cfg.agent_mode = os.getenv("THUAI9_AGENT_MODE", str(cfg.agent_mode))
    cfg.rule_profile = os.getenv("THUAI9_RULE_PROFILE", str(getattr(cfg, "rule_profile", "balanced")))
    cfg.min_role_duration_ms = int(os.getenv("THUAI9_MIN_ROLE_DURATION_MS", getattr(cfg, "min_role_duration_ms", 3000)))
    cfg.min_strategic_state_duration_ms = int(os.getenv("THUAI9_MIN_STRATEGIC_STATE_DURATION_MS", getattr(cfg, "min_strategic_state_duration_ms", 5000)))
    cfg.decision_interval_ms = int(os.getenv("THUAI9_DECISION_INTERVAL_MS", cfg.decision_interval_ms))
    cfg.team_id = int(os.getenv("THUAI9_TEAM_ID", cfg.team_id))
    cfg.log_path = Path(os.getenv("THUAI9_LOG_DIR", str(cfg.log_path)))
    cfg.checkpoint_path = Path(os.getenv("THUAI9_POLICY_CHECKPOINT", os.getenv("THUAI9_CHECKPOINT", str(cfg.checkpoint_path))))
    cfg.server_port = int(os.getenv("SERVER_PORT", cfg.server_port))
    cfg.log_path.mkdir(parents=True, exist_ok=True)
    cfg.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    return cfg
