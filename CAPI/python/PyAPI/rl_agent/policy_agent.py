from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.action_space import CHARACTER_ACTIONS, TEAM_ACTIONS, CharacterAction, TeamAction, character_action_mask, mask_as_list, team_action_mask
from PyAPI.rl_agent.macro_actions import ActionResult
from PyAPI.rl_agent.observation import build_observation, observation_to_vector
from PyAPI.rl_agent.reward import compute_reward
from PyAPI.rl_agent.rule_agent import RuleAgent
from PyAPI.rl_agent.utils import now_ms


class PolicyAgent(RuleAgent):
    def __init__(self, api, player_id: int, config):
        super().__init__(api, player_id, config)
        self._torch = None
        self._model = None
        self._fallback_warned = False
        self.deterministic = os.getenv("THUAI9_POLICY_DETERMINISTIC", "1") == "1"
        self._load_policy()

    def _load_policy(self) -> None:
        path = Path(self.config.checkpoint_path)
        if not path.exists():
            self._warn(f"policy checkpoint not found, fallback to rule: {path}")
            return
        try:
            import torch
            from PyAPI.rl_agent.models import THUAI9ActorCritic, THUAI9MAPPO

            ckpt = torch.load(path, map_location="cpu")
            obs_dim = int(ckpt.get("obs_dim", 64)) if isinstance(ckpt, dict) else 64
            action_dim = int(ckpt.get("action_dim", max(len(TEAM_ACTIONS), len(CHARACTER_ACTIONS)))) if isinstance(ckpt, dict) else max(len(TEAM_ACTIONS), len(CHARACTER_ACTIONS))
            hidden_dim = int(ckpt.get("hidden_dim", 128)) if isinstance(ckpt, dict) else 128
            if isinstance(ckpt, dict) and "mappo_approximation" in ckpt:
                model = THUAI9MAPPO(obs_dim=obs_dim, state_dim=int(ckpt.get("state_dim", obs_dim)), action_dim=action_dim, hidden_dim=hidden_dim)
            else:
                model = THUAI9ActorCritic(obs_dim=obs_dim, action_dim=action_dim, hidden_dim=hidden_dim)
            state = ckpt.get("model", ckpt) if isinstance(ckpt, dict) else ckpt
            model.load_state_dict(state, strict=False)
            model.eval()
            self._torch = torch
            self._model = model
        except Exception as exc:
            self._warn(f"failed to load policy checkpoint, fallback to rule: {exc}")
            self._model = None

    def _team_step(self, api) -> None:
        team_info = api.GetSelfInfo()
        if team_info is None:
            return
        self.config.team_id = team_info.teamID
        self.ensure_logger_team(team_info.teamID)
        if self._model is None or self._torch is None:
            return super()._team_step(api)
        local = self.tracker.player(self.player_id)
        now = now_ms()
        if now - local.last_decision_ms < self.config.decision_interval_ms:
            return
        local.last_decision_ms = now
        obs = build_observation(api, self.player_id, self.navigator, local, is_team=True)
        idx, log_prob, value = self._infer(obs.to_dict(), obs.action_mask, len(TEAM_ACTIONS))
        action = TEAM_ACTIONS[idx] if idx is not None else super()._choose_team_action(api, team_info)
        result = self.executor.run_team(api, team_info, action, obs.frame, self.config.max_characters)
        local.last_macro_action = action.name
        local.last_action_success = result.success
        if not result.success:
            local.invalid_actions += 1
        reward = compute_reward(api, obs, local, self.config, result.success)
        self.logger.write(obs, int(action), action.name, mask_as_list(team_action_mask(api, team_info, self.config.max_characters), TEAM_ACTIONS), result.success, reward, {"failure_reason": result.reason, "log_prob": log_prob, "value": value, "policy_checkpoint": str(self.config.checkpoint_path)})

    def _character_step(self, api) -> None:
        self_info = api.GetSelfInfo()
        if self_info is None or self_info.characterActiveState == THUAI9.CharacterState.Deceased:
            return
        self.config.team_id = self_info.teamID
        self.ensure_logger_team(self_info.teamID)
        game_map = api.GetFullMap()
        self.navigator.update(game_map)
        if self._model is None or self._torch is None:
            return super()._character_step(api)
        local = self.tracker.player(self.player_id)
        now = now_ms()
        if now - local.last_decision_ms < self.config.decision_interval_ms:
            return
        local.last_decision_ms = now
        obs = build_observation(api, self.player_id, self.navigator, local, is_team=False)
        if self_info.characterActiveState not in (THUAI9.CharacterState.Idle, THUAI9.CharacterState.NoneState):
            reward = compute_reward(api, obs, local, self.config, True)
            self.logger.write(obs, int(CharacterAction.IDLE), "WAIT_BUSY", obs.action_mask, True, reward, {"log_prob": 0.0, "value": 0.0})
            return
        idx, log_prob, value = self._infer(obs.to_dict(), obs.action_mask, len(CHARACTER_ACTIONS))
        action = CHARACTER_ACTIONS[idx] if idx is not None else super()._choose_character_action(api, self_info)
        result = self.executor.run_character(api, self_info, action, game_map, local)
        local.last_macro_action = action.name
        local.last_target = result.target
        local.last_action_success = result.success
        if result.target:
            self.tracker.assign(self.player_id, result.target)
        if not result.success:
            local.invalid_actions += 1
        reward = compute_reward(api, obs, local, self.config, result.success)
        self.logger.write(obs, int(action), action.name, obs.action_mask, result.success, reward, {"failure_reason": result.reason, "target": list(result.target) if result.target else None, "log_prob": log_prob, "value": value, "policy_checkpoint": str(self.config.checkpoint_path)})

    def _infer(self, obs_dict, mask: list[int], action_count: int) -> Tuple[Optional[int], float, float]:
        try:
            vec = observation_to_vector(obs_dict, getattr(self._model, "obs_dim", 64))
            obs_tensor = self._torch.tensor([vec], dtype=self._torch.float32)
            full_mask = list(mask[:action_count]) + [0] * max(0, getattr(self._model, "action_dim", action_count) - action_count)
            if not any(full_mask[:action_count]):
                return None, 0.0, 0.0
            action_mask = self._torch.tensor([full_mask[: getattr(self._model, "action_dim", action_count)]], dtype=self._torch.bool)
            with self._torch.no_grad():
                logits, value, _hidden = self._model(obs_tensor, action_mask=action_mask)
                dist = self._torch.distributions.Categorical(logits=logits[:, :action_count])
                action = logits[0, :action_count].argmax() if self.deterministic else dist.sample()[0]
                log_prob = dist.log_prob(action).item()
            return int(action.item()), float(log_prob), float(value.item())
        except Exception as exc:
            self._warn(f"policy inference failed, fallback action: {exc}")
            return None, 0.0, 0.0

    def _warn(self, msg: str) -> None:
        if self._fallback_warned:
            return
        self._fallback_warned = True
        try:
            self.api.Print("[rl_agent] " + msg)
        except Exception:
            print("[rl_agent] " + msg)
