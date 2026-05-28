from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.action_space import CharacterAction, TeamAction, character_action_mask, team_action_mask
from PyAPI.rl_agent.navigation import Navigator
from PyAPI.rl_agent.state_tracker import PlayerLocalState, StateTracker
from PyAPI.rl_agent.utils import accepted, angle_to, cell_of, goods_total, grid_center


@dataclass
class ActionResult:
    action: str
    success: bool
    reason: str = ""
    target: Optional[tuple[int, int]] = None


class MacroExecutor:
    def __init__(self, navigator: Navigator, tracker: StateTracker, move_time_ms: int = 220) -> None:
        self.nav = navigator
        self.tracker = tracker
        self.move_time_ms = move_time_ms

    def run_team(self, api, team_info: THUAI9.Team, action: TeamAction, frame: int, max_characters: int) -> ActionResult:
        mask = team_action_mask(api, team_info, max_characters)
        if not mask.get(action, False):
            return ActionResult(action.name, False, "masked")
        if action in {TeamAction.RECRUIT_CAR, TeamAction.RECRUIT_DRONE, TeamAction.RECRUIT_ROBOT}:
            build_type = {
                TeamAction.RECRUIT_CAR: THUAI9.CharacterType.AutonomousCar,
                TeamAction.RECRUIT_DRONE: THUAI9.CharacterType.Drone,
                TeamAction.RECRUIT_ROBOT: THUAI9.CharacterType.Robot,
            }[action]
            used = {c.playerID for c in api.GetCharacters()}
            for player_id in range(1, max_characters + 1):
                if player_id not in used:
                    return ActionResult(action.name, accepted(api.BuildCharacter(build_type, player_id)), "", None)
            return ActionResult(action.name, False, "no_slot")
        if action == TeamAction.PRODUCE_SEMICONDUCTOR:
            return ActionResult(action.name, accepted(api.ProduceGoods(THUAI9.GoodsType.Semiconductor, max(1, team_info.material // 10))))
        if action == TeamAction.PRODUCE_MEDICINE:
            return ActionResult(action.name, accepted(api.ProduceGoods(THUAI9.GoodsType.Medicine, max(1, team_info.material // 5))))
        if action == TeamAction.PRODUCE_TOYS:
            return ActionResult(action.name, accepted(api.ProduceGoods(THUAI9.GoodsType.Toys, max(1, team_info.material))))
        if action == TeamAction.UPGRADE_EFFICIENCY:
            return ActionResult(action.name, accepted(api.UplevelTech(THUAI9.TechType.IncreaseEfficiency)))
        if action == TeamAction.UPGRADE_MOVE_SPEED:
            return ActionResult(action.name, accepted(api.UplevelTech(THUAI9.TechType.IncreaseMoveSpeed)))
        if action == TeamAction.UPGRADE_ATTACK:
            return ActionResult(action.name, accepted(api.UplevelTech(THUAI9.TechType.IncreaseAttackPower)))
        return ActionResult(action.name, True, "idle")

    def run_character(self, api, self_info: THUAI9.Character, action: CharacterAction, game_map, state: PlayerLocalState) -> ActionResult:
        mask = character_action_mask(api, self_info, self.nav, game_map)
        if not mask.get(action, False):
            return ActionResult(action.name, False, "masked")
        origin = cell_of(self_info.x, self_info.y)
        if action == CharacterAction.HARVEST:
            return ActionResult(action.name, accepted(api.Harvest()))
        if action == CharacterAction.OCCUPY_CENTER:
            return ActionResult(action.name, accepted(api.Occupy()))
        if action == CharacterAction.SELL_GOODS:
            for goods_type, amount in self_info.goodsLoad.items():
                if amount > 0:
                    return ActionResult(action.name, accepted(api.Sell(goods_type, int(amount))))
            return ActionResult(action.name, False, "empty")
        if action == CharacterAction.LOAD_GOODS:
            room = max(0, self_info.carryCapacity - self_info.currentLoad)
            for goods_type in (THUAI9.GoodsType.Semiconductor, THUAI9.GoodsType.Medicine, THUAI9.GoodsType.Clothes, THUAI9.GoodsType.Toys, THUAI9.GoodsType.Food):
                if accepted(api.Load(goods_type, room)):
                    return ActionResult(action.name, True)
            return ActionResult(action.name, False, "no_goods")
        if action == CharacterAction.ATTACK_NEAREST_ENEMY:
            target = self._nearest_enemy(api, self_info, in_range_only=True)
            if target is None:
                return ActionResult(action.name, False, "no_enemy")
            return ActionResult(action.name, accepted(api.Common_Attack(target.playerID)), target=(cell_of(target.x, target.y)))
        target = self._target_for(api, self_info, action, origin)
        if target is None:
            return ActionResult(action.name, action == CharacterAction.IDLE, "no_target")
        moved = self._move_to(api, self_info, game_map, target)
        return ActionResult(action.name, moved, target=target)

    def _target_for(self, api, self_info: THUAI9.Character, action: CharacterAction, origin: tuple[int, int]) -> Optional[tuple[int, int]]:
        if action == CharacterAction.GO_RESOURCE:
            return self.nav.nearest_resource(api, origin, self.tracker.assigned_targets())
        if action == CharacterAction.GO_CENTER:
            return self.nav.nearest_center(api, origin, self_info.teamID, self.tracker.assigned_targets())
        if action == CharacterAction.GO_MARKET:
            return self.nav.nearest_market(api, origin, self.tracker.market_cursor)
        if action == CharacterAction.GO_FACTORY:
            return self.nav.own_factory(api, origin, self_info.teamID)
        if action == CharacterAction.PRESSURE_ENEMY_FACTORY:
            return self.nav.enemy_factory(api, origin, self_info.teamID)
        if action == CharacterAction.RETREAT:
            return self.nav.retreat_point(api, origin, self_info.teamID)
        if action == CharacterAction.GO_ENEMY:
            enemy = self._nearest_enemy(api, self_info, in_range_only=False)
            return cell_of(enemy.x, enemy.y) if enemy is not None else None
        return None

    def _move_to(self, api, self_info: THUAI9.Character, game_map, target: tuple[int, int]) -> bool:
        origin = cell_of(self_info.x, self_info.y)
        nxt = self.nav.next_step(game_map, origin, target) or target
        x, y = grid_center(nxt)
        return accepted(api.Move(self.move_time_ms, angle_to(self_info.x, self_info.y, x, y)))

    def _nearest_enemy(self, api, self_info: THUAI9.Character, in_range_only: bool):
        candidates = []
        for enemy in api.GetEnemyCharacters():
            if enemy.characterActiveState == THUAI9.CharacterState.Deceased:
                continue
            dist2 = (self_info.x - enemy.x) ** 2 + (self_info.y - enemy.y) ** 2
            if in_range_only and dist2 > self_info.commonAttackRange ** 2:
                continue
            candidates.append((enemy.hp, dist2, enemy))
        return min(candidates)[2] if candidates else None
