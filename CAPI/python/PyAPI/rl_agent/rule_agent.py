from __future__ import annotations

import random
from typing import Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.action_space import CHARACTER_ACTIONS, TEAM_ACTIONS, CharacterAction, TeamAction, character_action_mask, mask_as_list, team_action_mask
from PyAPI.rl_agent.agent import BaseTHUAI9Agent
from PyAPI.rl_agent.observation import build_observation
from PyAPI.rl_agent.reward import compute_reward
from PyAPI.rl_agent.utils import cell_of, goods_total, now_ms


class RuleAgent(BaseTHUAI9Agent):
    def step(self, api=None) -> None:
        api = api or self.api
        if self.player_id == 0:
            self._team_step(api)
        else:
            self._character_step(api)

    def _team_step(self, api) -> None:
        team_info = api.GetSelfInfo()
        if team_info is None:
            return
        self.config.team_id = team_info.teamID
        self.ensure_logger_team(team_info.teamID)
        local = self.tracker.player(self.player_id)
        now = now_ms()
        if now - local.last_decision_ms < self.config.decision_interval_ms:
            return
        local.last_decision_ms = now
        obs = build_observation(api, self.player_id, self.navigator, local, is_team=True)
        action = self._choose_team_action(api, team_info)
        result = self.executor.run_team(api, team_info, action, obs.frame, self.config.max_characters)
        local.last_macro_action = action.name
        local.last_action_success = result.success
        if not result.success:
            local.invalid_actions += 1
        reward = compute_reward(api, obs, local, self.config, result.success)
        self.logger.write(obs, int(action), action.name, mask_as_list(team_action_mask(api, team_info, self.config.max_characters), TEAM_ACTIONS), result.success, reward, {"failure_reason": result.reason})

    def _character_step(self, api) -> None:
        self_info = api.GetSelfInfo()
        if self_info is None or self_info.characterActiveState == THUAI9.CharacterState.Deceased:
            return
        self.config.team_id = self_info.teamID
        self.ensure_logger_team(self_info.teamID)
        game_map = api.GetFullMap()
        self.navigator.update(game_map)
        local = self.tracker.player(self.player_id)
        now = now_ms()
        if now - local.last_decision_ms < self.config.decision_interval_ms:
            return
        local.last_decision_ms = now
        obs = build_observation(api, self.player_id, self.navigator, local, is_team=False)
        if self_info.characterActiveState not in (THUAI9.CharacterState.Idle, THUAI9.CharacterState.NoneState):
            reward = compute_reward(api, obs, local, self.config, True)
            self.logger.write(obs, int(CharacterAction.IDLE), "WAIT_BUSY", obs.action_mask, True, reward)
            return
        action = self._choose_character_action(api, self_info)
        result = self.executor.run_character(api, self_info, action, game_map, local)
        local.last_macro_action = action.name
        local.last_target = result.target
        local.last_action_success = result.success
        if result.target:
            self.tracker.assign(self.player_id, result.target)
        if not result.success:
            local.invalid_actions += 1
        reward = compute_reward(api, obs, local, self.config, result.success)
        self.logger.write(obs, int(action), action.name, obs.action_mask, result.success, reward, {"failure_reason": result.reason, "target": list(result.target) if result.target else None})

    def _choose_team_action(self, api, team_info: THUAI9.Team) -> TeamAction:
        active_chars = [c for c in api.GetCharacters() if c.characterActiveState != THUAI9.CharacterState.Deceased]
        ids = {c.playerID for c in active_chars}
        if len(active_chars) < 2 and team_info.computePower >= 50:
            return TeamAction.RECRUIT_DRONE if 1 not in ids else TeamAction.RECRUIT_ROBOT
        if len(active_chars) < 3 and team_info.computePower >= 50:
            return TeamAction.RECRUIT_CAR
        if team_info.material >= 20:
            return TeamAction.PRODUCE_SEMICONDUCTOR
        if team_info.material >= 8:
            return TeamAction.PRODUCE_MEDICINE
        if team_info.material >= 1:
            return TeamAction.PRODUCE_TOYS
        if team_info.computePower >= 80:
            order = [TeamAction.UPGRADE_EFFICIENCY, TeamAction.UPGRADE_MOVE_SPEED, TeamAction.UPGRADE_ATTACK]
            action = order[self.tracker.tech_cursor % len(order)]
            self.tracker.tech_cursor += 1
            return action
        return TeamAction.SAVE_COMPUTE

    def _choose_character_action(self, api, self_info: THUAI9.Character) -> CharacterAction:
        origin = cell_of(self_info.x, self_info.y)
        enemies = [e for e in api.GetEnemyCharacters() if e.characterActiveState != THUAI9.CharacterState.Deceased]
        low_hp = self_info.hp > 0 and self_info.hp < 45
        if low_hp:
            return CharacterAction.RETREAT
        if any((self_info.x - e.x) ** 2 + (self_info.y - e.y) ** 2 <= self_info.commonAttackRange ** 2 for e in enemies):
            return CharacterAction.ATTACK_NEAREST_ENEMY
        if goods_total(self_info.goodsLoad) > 0:
            market = self.navigator.nearest_market(api, origin, self.tracker.market_cursor)
            if market is not None:
                return CharacterAction.SELL_GOODS if self.navigator.cache.ready and max(abs(origin[0] - market[0]), abs(origin[1] - market[1])) <= 1 else CharacterAction.GO_MARKET
        own_factory = self.navigator.own_factory(api, origin, self_info.teamID)
        if own_factory is not None and max(abs(origin[0] - own_factory[0]), abs(origin[1] - own_factory[1])) <= 1 and self_info.currentLoad < self_info.carryCapacity:
            return CharacterAction.LOAD_GOODS
        role = self._role(self_info)
        if role in {"center", "pressure"}:
            center = self.navigator.nearest_center(api, origin, self_info.teamID, self.tracker.assigned_targets())
            if center is not None:
                return CharacterAction.OCCUPY_CENTER if max(abs(origin[0] - center[0]), abs(origin[1] - center[1])) <= 1 else CharacterAction.GO_CENTER
            if enemies:
                return CharacterAction.GO_ENEMY
            if role == "pressure" and self_info.hp > 80:
                return CharacterAction.PRESSURE_ENEMY_FACTORY
        resource = self.navigator.nearest_resource(api, origin, self.tracker.assigned_targets())
        if resource is not None and self_info.currentLoad < self_info.carryCapacity:
            return CharacterAction.HARVEST if max(abs(origin[0] - resource[0]), abs(origin[1] - resource[1])) <= 1 else CharacterAction.GO_RESOURCE
        if own_factory is not None:
            return CharacterAction.GO_FACTORY
        return CharacterAction.IDLE

    def _role(self, self_info: THUAI9.Character) -> str:
        if self_info.playerID == 1:
            return "economy"
        if self_info.playerID == 2:
            return "center"
        return "pressure" if self_info.characterType in (THUAI9.CharacterType.Robot, THUAI9.CharacterType.AutonomousCar) else "economy"


class RandomAgent(RuleAgent):
    def _choose_team_action(self, api, team_info: THUAI9.Team) -> TeamAction:
        mask = team_action_mask(api, team_info, self.config.max_characters)
        legal = [a for a, ok in mask.items() if ok]
        return random.choice(legal or [TeamAction.IDLE])

    def _choose_character_action(self, api, self_info: THUAI9.Character) -> CharacterAction:
        game_map = api.GetFullMap()
        self.navigator.update(game_map)
        mask = character_action_mask(api, self_info, self.navigator, game_map)
        legal = [a for a, ok in mask.items() if ok]
        return random.choice(legal or [CharacterAction.IDLE])
