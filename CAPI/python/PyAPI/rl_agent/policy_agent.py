from __future__ import annotations

from pathlib import Path
from typing import Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.action_space import CHARACTER_ACTIONS, TEAM_ACTIONS, CharacterAction, TeamAction
from PyAPI.rl_agent.observation import build_observation
from PyAPI.rl_agent.rule_agent import RuleAgent
from PyAPI.rl_agent.utils import now_ms


class PolicyAgent(RuleAgent):
    def __init__(self, api, player_id: int, config):
        super().__init__(api, player_id, config)
        self._torch = None
        self._model = None
        self._load_policy()

    def _load_policy(self) -> None:
        path = Path(self.config.checkpoint_path)
        if not path.exists():
            return
        try:
            import torch
            from PyAPI.rl_agent.models import THUAI9PolicyNet

            ckpt = torch.load(path, map_location="cpu")
            obs_dim = int(ckpt.get("obs_dim", 64)) if isinstance(ckpt, dict) else 64
            act_dim = max(len(TEAM_ACTIONS), len(CHARACTER_ACTIONS))
            model = THUAI9PolicyNet(obs_dim=obs_dim, action_dim=act_dim)
            state = ckpt.get("model", ckpt) if isinstance(ckpt, dict) else ckpt
            model.load_state_dict(state, strict=False)
            model.eval()
            self._torch = torch
            self._model = model
        except Exception:
            self._model = None

    def _choose_team_action(self, api, team_info: THUAI9.Team) -> TeamAction:
        if self._model is None or self._torch is None:
            return super()._choose_team_action(api, team_info)
        local = self.tracker.player(self.player_id)
        obs = build_observation(api, self.player_id, self.navigator, local, is_team=True)
        idx = self._infer(obs.action_mask, len(TEAM_ACTIONS))
        return TEAM_ACTIONS[idx] if idx is not None else super()._choose_team_action(api, team_info)

    def _choose_character_action(self, api, self_info: THUAI9.Character) -> CharacterAction:
        if self._model is None or self._torch is None:
            return super()._choose_character_action(api, self_info)
        local = self.tracker.player(self.player_id)
        obs = build_observation(api, self.player_id, self.navigator, local, is_team=False)
        idx = self._infer(obs.action_mask, len(CHARACTER_ACTIONS))
        return CHARACTER_ACTIONS[idx] if idx is not None else super()._choose_character_action(api, self_info)

    def _infer(self, mask: list[int], action_count: int) -> Optional[int]:
        try:
            features = self._torch.zeros(1, getattr(self._model, "obs_dim", 64), dtype=self._torch.float32)
            action_mask = self._torch.tensor(mask[:action_count], dtype=self._torch.bool).unsqueeze(0)
            with self._torch.no_grad():
                logits, _value, _hidden = self._model(features, action_mask=action_mask)
            return int(logits[0, :action_count].argmax().item())
        except Exception:
            return None
