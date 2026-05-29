from __future__ import annotations

import os
import random
from typing import Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.action_space import CHARACTER_ACTIONS, TEAM_ACTIONS, CharacterAction, TeamAction, character_action_mask, mask_as_list, team_action_mask
from PyAPI.rl_agent.center_control import CenterControlManager
from PyAPI.rl_agent.combat_manager import CombatManager
from PyAPI.rl_agent.agent import BaseTHUAI9Agent
from PyAPI.rl_agent.interaction_contract import InteractionContext
from PyAPI.rl_agent.observation import build_observation
from PyAPI.rl_agent.production_manager import ProductionManager
from PyAPI.rl_agent.recruitment_manager import RecruitmentManager
from PyAPI.rl_agent.reward import compute_reward
from PyAPI.rl_agent.state_tracker import EconomyState, PlayerLocalState
from PyAPI.rl_agent.strategic_fsm import RoleAssignment, StrategicFSM
from PyAPI.rl_agent.utils import cell_of, goods_total, near, now_ms


class RuleAgent(BaseTHUAI9Agent):
    def __init__(self, api, player_id: int, config):
        super().__init__(api, player_id, config)
        self.production_manager = ProductionManager()
        self.recruitment_manager = RecruitmentManager()
        self.strategic_fsm = StrategicFSM(config.min_strategic_state_duration_ms, config.min_role_duration_ms)
        self.center_control = CenterControlManager()
        self.combat_manager = CombatManager()
        self.rule_profile = (os.getenv("THUAI9_RULE_PROFILE", "") or getattr(config, "rule_profile", "balanced") or "balanced").strip().lower()
        if config.agent_mode == "economy_debug":
            self.rule_profile = "economy_only"

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
        strategic = self.strategic_fsm.update(api, self.tracker, team_info.teamID, self.rule_profile)

        recruit = self.recruitment_manager.choose(api, team_info, self.rule_profile, strategic.state, self.tracker.first_sell_done, self.config.max_characters)
        action = recruit.action
        result = self.executor.run_team(api, team_info, action, obs.frame, self.config.max_characters)
        macro_name = action.name
        extra = {
            "failure_reason": result.reason,
            "macro_task": "TEAM_SCHEDULER",
            "contract_reason": result.reason,
            "strategic_state": strategic.state.value,
            "role_assignment": "TEAM",
            "role_switch_reason": self.tracker.role_switch_reason,
            "recruit_decision": recruit.action.name,
            "recruit_character_type": getattr(recruit.character_type, "name", None),
            "recruit_reason": recruit.reason,
            "recruit_success": None,
        }

        if action in {TeamAction.SAVE_COMPUTE, TeamAction.IDLE}:
            ctx = InteractionContext.team(api, team_info, self.navigator, self.config.max_characters)
            success, reason, goods = self.production_manager.maybe_produce(api, ctx)
            if goods is not None:
                blocked = (not success) and reason in {"factory_busy", "factory_storage_full", "no_material", "cooldown_active", "no_production_needed"}
                macro_name = f"PRODUCE_{goods.name.upper()}" if not blocked else "TEAM_IDLE"
                result.success = True if blocked else success
                result.reason = reason
                extra.update({
                    "failure_reason": reason,
                    "contract_reason": reason,
                    "precondition_ok": not blocked,
                    "goods_type": goods.name,
                    "economy_event": "produce_succeeded" if success else ("produce_blocked" if blocked else "produce_failed"),
                })
            elif self.rule_profile == "economy_only":
                result.success = True
                result.reason = reason
                macro_name = "TEAM_IDLE"
                extra.update({"failure_reason": reason, "contract_reason": reason})

        if action in {TeamAction.RECRUIT_CAR, TeamAction.RECRUIT_DRONE, TeamAction.RECRUIT_ROBOT}:
            extra["recruit_success"] = result.success
        local.last_macro_action = macro_name
        local.last_action_success = result.success
        if not result.success and result.reason not in {"cooldown_active", "no_production_needed"}:
            local.invalid_actions += 1
            local.failure_count += 1
        else:
            local.failure_count = 0
        reward = compute_reward(api, obs, local, self.config, result.success)
        self._debug(api, local, macro_name, result.reason, obs)
        self.logger.write(obs, int(action), macro_name, mask_as_list(team_action_mask(api, team_info, self.config.max_characters), TEAM_ACTIONS), result.success, reward, extra)

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
        strategic = self.strategic_fsm.update(api, self.tracker, self_info.teamID, self.rule_profile)
        role_assignment = RoleAssignment(self.tracker.role_assignment_by_player.get(self_info.playerID, strategic.roles.get(self_info.playerID, RoleAssignment.IDLE).value))
        role = self._role(self_info, role_assignment)
        local.role = role_assignment.value

        if self_info.characterActiveState not in (THUAI9.CharacterState.Idle, THUAI9.CharacterState.NoneState):
            reward = compute_reward(api, obs, local, self.config, True)
            self.logger.write(obs, int(CharacterAction.IDLE), "WAIT_BUSY", obs.action_mask, True, reward, {
                "failure_reason": "character_busy",
                "contract_reason": "character_busy",
                "fsm_state": local.economy_state.value if role == "economy" else None,
                "center_fsm_state": local.center_fsm_state if role == "center" else None,
                "macro_task": local.role,
                "strategic_state": strategic.state.value,
                "role_assignment": role_assignment.value,
                "role_switch_reason": self.tracker.role_switch_reason,
            })
            return

        center_decision = None
        combat_decision = None
        if role == "economy":
            action = self._choose_economy_action(api, self_info, local, game_map, obs)
        elif role == "center":
            center_decision = self.center_control.choose_action(api, self_info, self.navigator, game_map, local, self.tracker)
            action = center_decision.action
        elif role in {"defense", "hunt", "pressure", "retreat", "scout"}:
            combat_decision = self.combat_manager.choose_action(api, self_info, self.navigator, role_assignment)
            action = combat_decision.action
        else:
            action = self._choose_character_action(api, self_info)
        result = self.executor.run_character(api, self_info, action, game_map, local)
        local.last_macro_action = action.name
        local.last_target = result.target
        local.last_action_success = result.success
        cur_cell = cell_of(self_info.x, self_info.y)
        if local.last_cell == cur_cell and action.name.startswith("GO_"):
            local.stuck_count += 1
        else:
            local.stuck_count = 0
        local.last_cell = cur_cell
        if result.target:
            self.tracker.assign(self.player_id, result.target)
        if role == "economy":
            self._advance_economy_after(api, self_info, local, action, result, obs)
        if center_decision is not None:
            self.center_control.after_action(local, action, result.success)
            if local.center_occupied and not self.tracker.first_center_occupied_time:
                self.tracker.first_center_occupied_time = now_ms()
        if not result.success:
            local.invalid_actions += 1
            local.failure_count += 1
        else:
            local.failure_count = 0
        if local.failure_count >= 3 or local.stuck_count >= 10:
            self._set_economy_state(local, EconomyState.RECOVER_FROM_FAILURE)
            self.tracker.clear_assignment(self.player_id)
            local.current_target = None
            local.failure_count = 0
            local.stuck_count = 0
        reward = compute_reward(api, obs, local, self.config, result.success)
        self._debug(api, local, action.name, result.reason, obs)
        self.logger.write(obs, int(action), action.name, obs.action_mask, result.success, reward, {
            "failure_reason": result.reason,
            "contract_reason": result.reason,
            "target": list(result.target) if result.target else None,
            "macro_task": local.role,
            "strategic_state": strategic.state.value,
            "role_assignment": role_assignment.value,
            "role_switch_reason": self.tracker.role_switch_reason,
            "fsm_state": local.economy_state.value if role == "economy" else None,
            "local_fsm_state": local.economy_state.value if role == "economy" else (local.center_fsm_state if role == "center" else None),
            "center_fsm_state": local.center_fsm_state if role == "center" else None,
            "target_type": self._target_type(action),
            "target_cell": list(result.target) if result.target else (list(center_decision.target) if center_decision and center_decision.target else None),
            "target_id": combat_decision.target_id if combat_decision else None,
            "center_action_reason": center_decision.reason if center_decision else None,
            "combat_action_reason": combat_decision.reason if combat_decision else None,
            "center_occupied": bool(local.center_occupied),
            "economy_loop_count": local.loop_count,
        })

    def _target_type(self, action: CharacterAction) -> Optional[str]:
        if action in {CharacterAction.GO_RESOURCE, CharacterAction.HARVEST}:
            return "resource"
        if action in {CharacterAction.GO_MARKET, CharacterAction.SELL_GOODS}:
            return "market"
        if action in {CharacterAction.GO_CENTER, CharacterAction.OCCUPY_CENTER}:
            return "center"
        if action in {CharacterAction.GO_FACTORY, CharacterAction.RETREAT, CharacterAction.LOAD_GOODS}:
            return "factory"
        if action in {CharacterAction.GO_ENEMY, CharacterAction.ATTACK_NEAREST_ENEMY}:
            return "enemy"
        if action == CharacterAction.PRESSURE_ENEMY_FACTORY:
            return "enemy_factory"
        return None

    def _choose_team_action(self, api, team_info: THUAI9.Team) -> TeamAction:
        active_chars = [c for c in api.GetCharacters() if c.characterActiveState != THUAI9.CharacterState.Deceased]
        by_id = {c.playerID: c for c in active_chars}
        if self.rule_profile == "economy_only":
            if team_info.computePower >= 50 and 1 not in by_id:
                return TeamAction.RECRUIT_CAR
            return TeamAction.SAVE_COMPUTE
        if team_info.computePower >= 50:
            if 1 not in by_id:
                return TeamAction.RECRUIT_CAR
            if 2 not in by_id:
                return TeamAction.RECRUIT_DRONE
            if len(active_chars) < 3:
                if team_info.score < 500 or team_info.material < 20:
                    return TeamAction.RECRUIT_CAR
                return TeamAction.RECRUIT_ROBOT
        return TeamAction.SAVE_COMPUTE

    def _choose_economy_action(self, api, self_info: THUAI9.Character, local: PlayerLocalState, game_map, obs) -> CharacterAction:
        origin = cell_of(self_info.x, self_info.y)
        material = int(obs.team_state.get("material") or 0)
        if local.state_enter_ms == 0:
            local.state_enter_ms = now_ms()
        if goods_total(self_info.goodsLoad) > 0 and local.economy_state not in {EconomyState.SELECT_MARKET, EconomyState.MOVE_TO_MARKET, EconomyState.ALIGN_MARKET, EconomyState.SELL_GOODS}:
            self._set_economy_state(local, EconomyState.SELECT_MARKET)
        if local.economy_state == EconomyState.SELECT_RESOURCE:
            target = self._select_reachable_resource(api, game_map, origin, local)
            if target is None:
                local.blocked_economy_targets.clear()
                target = self._select_reachable_resource(api, game_map, origin, local)
            if target is None:
                return CharacterAction.IDLE
            local.economy_target_resource = target
            local.current_target = target
            self.tracker.assign(self.player_id, target)
            self._set_economy_state(local, EconomyState.MOVE_TO_RESOURCE)
            return CharacterAction.GO_RESOURCE
        if local.economy_state == EconomyState.MOVE_TO_RESOURCE:
            target = local.economy_target_resource
            if target is None:
                self._set_economy_state(local, EconomyState.SELECT_RESOURCE)
                return CharacterAction.IDLE
            if near(origin, target):
                self._set_economy_state(local, EconomyState.ALIGN_RESOURCE)
                return CharacterAction.IDLE
            return CharacterAction.GO_RESOURCE
        if local.economy_state == EconomyState.ALIGN_RESOURCE:
            target = local.economy_target_resource
            if target is not None and near(origin, target):
                self._set_economy_state(local, EconomyState.START_HARVEST)
                return CharacterAction.HARVEST
            self._set_economy_state(local, EconomyState.MOVE_TO_RESOURCE)
            return CharacterAction.GO_RESOURCE
        if local.economy_state == EconomyState.START_HARVEST:
            return CharacterAction.HARVEST
        if local.economy_state == EconomyState.WAIT_HARVEST:
            elapsed = now_ms() - local.state_enter_ms
            resource_done = self._resource_depleted(api, local.economy_target_resource)
            if material > local.material_at_harvest_start or elapsed > 9000 or resource_done:
                local.economy_target_factory = self.navigator.own_factory(api, origin, self_info.teamID)
                self._set_economy_state(local, EconomyState.RETURN_FACTORY)
                return CharacterAction.GO_FACTORY
            return CharacterAction.IDLE
        if local.economy_state == EconomyState.RETURN_FACTORY:
            factory = local.economy_target_factory or self.navigator.own_factory(api, origin, self_info.teamID)
            local.economy_target_factory = factory
            if factory is None:
                return CharacterAction.IDLE
            if near(origin, factory):
                self._set_economy_state(local, EconomyState.ALIGN_FACTORY)
                return CharacterAction.IDLE
            return CharacterAction.GO_FACTORY
        if local.economy_state == EconomyState.ALIGN_FACTORY:
            factory = local.economy_target_factory or self.navigator.own_factory(api, origin, self_info.teamID)
            if factory is None or not near(origin, factory):
                self._set_economy_state(local, EconomyState.RETURN_FACTORY)
                return CharacterAction.GO_FACTORY
            if self._factory_has_goods(api, factory) and self_info.currentLoad < self_info.carryCapacity:
                self._set_economy_state(local, EconomyState.LOAD_GOODS)
                return CharacterAction.LOAD_GOODS
            self._set_economy_state(local, EconomyState.WAIT_PRODUCTION)
            return CharacterAction.IDLE
        if local.economy_state == EconomyState.WAIT_PRODUCTION:
            factory = local.economy_target_factory or self.navigator.own_factory(api, origin, self_info.teamID)
            local.economy_target_factory = factory
            if factory is None or not near(origin, factory):
                self._set_economy_state(local, EconomyState.RETURN_FACTORY)
                return CharacterAction.GO_FACTORY
            if self._factory_has_goods(api, factory) and self_info.currentLoad < self_info.carryCapacity:
                self._set_economy_state(local, EconomyState.LOAD_GOODS)
                return CharacterAction.LOAD_GOODS
            if now_ms() - local.state_enter_ms > 18000 and material <= 0:
                self._set_economy_state(local, EconomyState.SELECT_RESOURCE)
            return CharacterAction.IDLE
        if local.economy_state == EconomyState.LOAD_GOODS:
            return CharacterAction.LOAD_GOODS
        if local.economy_state == EconomyState.SELECT_MARKET:
            market = self.navigator.nearest_market(api, origin, self.tracker.market_cursor)
            if market is None:
                return CharacterAction.IDLE
            local.economy_target_market = market
            local.current_target = market
            self._set_economy_state(local, EconomyState.MOVE_TO_MARKET)
            return CharacterAction.GO_MARKET
        if local.economy_state == EconomyState.MOVE_TO_MARKET:
            market = local.economy_target_market
            if market is None:
                self._set_economy_state(local, EconomyState.SELECT_MARKET)
                return CharacterAction.IDLE
            if near(origin, market):
                self._set_economy_state(local, EconomyState.ALIGN_MARKET)
                return CharacterAction.IDLE
            return CharacterAction.GO_MARKET
        if local.economy_state == EconomyState.ALIGN_MARKET:
            market = local.economy_target_market
            if market is not None and near(origin, market):
                self._set_economy_state(local, EconomyState.SELL_GOODS)
                return CharacterAction.SELL_GOODS
            self._set_economy_state(local, EconomyState.MOVE_TO_MARKET)
            return CharacterAction.GO_MARKET
        if local.economy_state == EconomyState.SELL_GOODS:
            return CharacterAction.SELL_GOODS
        if local.economy_state == EconomyState.RECOVER_FROM_FAILURE:
            if self_info.hp > 0 and self_info.hp < 50:
                return CharacterAction.RETREAT
            if local.economy_target_resource is not None:
                local.blocked_economy_targets.add(local.economy_target_resource)
            local.economy_target_resource = None
            local.economy_target_market = None
            self.tracker.clear_assignment(self.player_id)
            self._set_economy_state(local, EconomyState.SELECT_RESOURCE)
            return CharacterAction.IDLE
        return CharacterAction.IDLE

    def _advance_economy_after(self, api, self_info: THUAI9.Character, local: PlayerLocalState, action: CharacterAction, result, obs) -> None:
        if action == CharacterAction.HARVEST and result.success:
            local.material_at_harvest_start = int(obs.team_state.get("material") or 0)
            self._set_economy_state(local, EconomyState.WAIT_HARVEST)
            return
        if action == CharacterAction.LOAD_GOODS and result.success:
            self._set_economy_state(local, EconomyState.SELECT_MARKET)
            return
        if action == CharacterAction.SELL_GOODS and result.success:
            local.loop_count += 1
            self.tracker.market_cursor += 1
            local.economy_target_market = None
            local.economy_target_resource = None
            self.tracker.clear_assignment(self.player_id)
            self._set_economy_state(local, EconomyState.SELECT_RESOURCE)
            return
        if not result.success and action in {CharacterAction.HARVEST, CharacterAction.LOAD_GOODS, CharacterAction.SELL_GOODS, CharacterAction.OCCUPY_CENTER}:
            if local.failure_count >= 1:
                self._set_economy_state(local, EconomyState.RECOVER_FROM_FAILURE)

    def _set_economy_state(self, local: PlayerLocalState, state: EconomyState) -> None:
        if local.economy_state != state:
            local.economy_state = state
            local.state_enter_ms = now_ms()

    def _select_reachable_resource(self, api, game_map, origin: tuple[int, int], local: PlayerLocalState) -> Optional[tuple[int, int]]:
        avoid = self.tracker.assigned_targets() | local.blocked_economy_targets
        candidates = []
        for cell in self.navigator.cache.resources:
            if cell in local.blocked_economy_targets:
                continue
            state = api.GetResourceState(*cell)
            if state is None or state.state == THUAI9.ResourceState.Harvested:
                continue
            step = self.navigator.next_step(game_map, origin, cell)
            if not near(origin, cell) and step is None:
                continue
            penalty = 8 if cell in avoid else 0
            candidates.append((abs(origin[0] - cell[0]) + abs(origin[1] - cell[1]) + penalty, cell))
        return min(candidates)[1] if candidates else None

    def _factory_has_goods(self, api, factory_cell: Optional[tuple[int, int]]) -> bool:
        if factory_cell is None:
            return False
        factory = api.GetFactoryState(*factory_cell)
        if factory is None:
            return False
        return any(int(v) > 0 for v in factory.productInventory.values())

    def _resource_depleted(self, api, resource_cell: Optional[tuple[int, int]]) -> bool:
        if resource_cell is None:
            return False
        state = api.GetResourceState(*resource_cell)
        return state is not None and state.state == THUAI9.ResourceState.Harvested

    def _choose_character_action(self, api, self_info: THUAI9.Character) -> CharacterAction:
        origin = cell_of(self_info.x, self_info.y)
        enemies = [e for e in api.GetEnemyCharacters() if e.characterActiveState != THUAI9.CharacterState.Deceased]
        role = self._role(self_info)
        low_hp = self_info.hp > 0 and self_info.hp < max(45, self_info.commonAttack * 2)
        if low_hp:
            return CharacterAction.IDLE
        if any((self_info.x - e.x) ** 2 + (self_info.y - e.y) ** 2 <= self_info.commonAttackRange ** 2 for e in enemies):
            return CharacterAction.ATTACK_NEAREST_ENEMY
        if goods_total(self_info.goodsLoad) > 0:
            market = self.navigator.nearest_market(api, origin, self.tracker.market_cursor)
            if market is not None:
                return CharacterAction.SELL_GOODS if near(origin, market) else CharacterAction.GO_MARKET
        own_factory = self.navigator.own_factory(api, origin, self_info.teamID)
        if own_factory is not None and near(origin, own_factory) and self_info.currentLoad < self_info.carryCapacity and self._factory_has_goods(api, own_factory):
            return CharacterAction.LOAD_GOODS
        if role in {"center", "pressure"}:
            center = self.navigator.nearest_center(api, origin, self_info.teamID, self.tracker.assigned_targets())
            if center is not None:
                return CharacterAction.OCCUPY_CENTER if near(origin, center) else CharacterAction.GO_CENTER
            if enemies:
                return CharacterAction.GO_ENEMY
            if role == "pressure" and self_info.hp > 80:
                return CharacterAction.PRESSURE_ENEMY_FACTORY
        resource = self.navigator.nearest_resource(api, origin, self.tracker.assigned_targets())
        if resource is not None:
            return CharacterAction.HARVEST if near(origin, resource) else CharacterAction.GO_RESOURCE
        if own_factory is not None:
            return CharacterAction.GO_FACTORY
        return CharacterAction.IDLE

    def _role(self, self_info: THUAI9.Character, assignment: Optional[RoleAssignment] = None) -> str:
        if assignment is not None:
            return {
                RoleAssignment.ECONOMY: "economy",
                RoleAssignment.CENTER: "center",
                RoleAssignment.DEFENSE: "defense",
                RoleAssignment.HUNT: "hunt",
                RoleAssignment.PRESSURE_FACTORY: "pressure",
                RoleAssignment.RETREAT: "retreat",
                RoleAssignment.SCOUT: "scout",
                RoleAssignment.IDLE: "idle",
            }.get(assignment, "idle")
        if self.rule_profile == "economy_only":
            return "economy" if self_info.playerID == 1 else "idle"
        if self_info.playerID == 1 or self_info.characterType == THUAI9.CharacterType.AutonomousCar:
            return "economy"
        if self_info.playerID == 2 or self_info.characterType == THUAI9.CharacterType.Drone:
            return "center"
        return "pressure" if self_info.characterType == THUAI9.CharacterType.Robot else "economy"

    def _debug(self, api, local, action: str, reason: str, obs) -> None:
        if os.getenv("THUAI9_RL_DEBUG", "0") != "1":
            return
        try:
            api.Print(
                f"[rl_rule] p={self.player_id} task={local.role} fsm={getattr(local.economy_state, 'value', None)} "
                f"action={action} target={local.last_target} ok={local.last_action_success} fail={reason} "
                f"score={obs.team_state.get('score')} compute={obs.team_state.get('compute_power')} "
                f"mat={obs.team_state.get('material')} hp={obs.team_state.get('factory_hp')} mask={obs.action_mask}"
            )
        except Exception:
            pass


class RandomAgent(RuleAgent):
    def _target_type(self, action: CharacterAction) -> Optional[str]:
        if action in {CharacterAction.GO_RESOURCE, CharacterAction.HARVEST}:
            return "resource"
        if action in {CharacterAction.GO_MARKET, CharacterAction.SELL_GOODS}:
            return "market"
        if action in {CharacterAction.GO_CENTER, CharacterAction.OCCUPY_CENTER}:
            return "center"
        if action in {CharacterAction.GO_FACTORY, CharacterAction.RETREAT, CharacterAction.LOAD_GOODS}:
            return "factory"
        if action in {CharacterAction.GO_ENEMY, CharacterAction.ATTACK_NEAREST_ENEMY}:
            return "enemy"
        if action == CharacterAction.PRESSURE_ENEMY_FACTORY:
            return "enemy_factory"
        return None

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
