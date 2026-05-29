from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.action_space import CharacterAction
from PyAPI.rl_agent.strategic_fsm import RoleAssignment
from PyAPI.rl_agent.utils import cell_of, near


@dataclass
class CombatDecision:
    action: CharacterAction
    reason: str
    target_id: Optional[int] = None
    target_cell: Optional[tuple[int, int]] = None


class CombatManager:
    def choose_action(self, api, self_info: THUAI9.Character, nav, role_assignment: RoleAssignment) -> CombatDecision:
        origin = cell_of(self_info.x, self_info.y)
        if self.should_retreat(self_info):
            return CombatDecision(CharacterAction.RETREAT, "low_hp_retreat")
        enemies = [e for e in api.GetEnemyCharacters() if e.characterActiveState != THUAI9.CharacterState.Deceased]
        own_factory = nav.own_factory(api, origin, self_info.teamID)
        if role_assignment == RoleAssignment.DEFENSE:
            target = self._nearest_enemy(enemies, self_info, near_cell=own_factory, radius=5) or self._nearest_enemy(enemies, self_info)
            if target is not None:
                if self._in_attack_range(self_info, target):
                    return CombatDecision(CharacterAction.ATTACK_NEAREST_ENEMY, "defense_attack_enemy", target.playerID, cell_of(target.x, target.y))
                return CombatDecision(CharacterAction.GO_ENEMY, "defense_chase_enemy", target.playerID, cell_of(target.x, target.y))
            return CombatDecision(CharacterAction.GO_FACTORY if own_factory else CharacterAction.IDLE, "defense_hold_factory", target_cell=own_factory)
        target = self._low_hp_enemy(enemies) or self._nearest_enemy(enemies, self_info)
        if target is not None and role_assignment in {RoleAssignment.HUNT, RoleAssignment.PRESSURE_FACTORY, RoleAssignment.SCOUT}:
            if self._in_attack_range(self_info, target):
                return CombatDecision(CharacterAction.ATTACK_NEAREST_ENEMY, "attack_visible_enemy", target.playerID, cell_of(target.x, target.y))
            if self._local_advantage(api, self_info, target):
                return CombatDecision(CharacterAction.GO_ENEMY, "chase_with_advantage", target.playerID, cell_of(target.x, target.y))
        if role_assignment == RoleAssignment.PRESSURE_FACTORY:
            return CombatDecision(CharacterAction.PRESSURE_ENEMY_FACTORY, "pressure_enemy_factory")
        return CombatDecision(CharacterAction.IDLE, "no_combat_target")

    def should_retreat(self, self_info: THUAI9.Character) -> bool:
        return self_info.hp > 0 and self_info.hp < max(35, self_info.commonAttack * 2)

    def _nearest_enemy(self, enemies, self_info, near_cell=None, radius: int = 99):
        candidates = []
        for enemy in enemies:
            ecell = cell_of(enemy.x, enemy.y)
            if near_cell is not None and not near(ecell, near_cell, radius):
                continue
            dist = (self_info.x - enemy.x) ** 2 + (self_info.y - enemy.y) ** 2
            candidates.append((dist, enemy))
        return min(candidates)[1] if candidates else None

    def _low_hp_enemy(self, enemies):
        candidates = [(e.hp, e) for e in enemies if e.hp > 0 and e.hp <= 60]
        return min(candidates)[1] if candidates else None

    def _in_attack_range(self, self_info, enemy) -> bool:
        return (self_info.x - enemy.x) ** 2 + (self_info.y - enemy.y) ** 2 <= self_info.commonAttackRange ** 2

    def _local_advantage(self, api, self_info, enemy) -> bool:
        allies = [c for c in api.GetCharacters() if c.characterActiveState != THUAI9.CharacterState.Deceased]
        ally_hp = sum(c.hp for c in allies if near(cell_of(c.x, c.y), cell_of(enemy.x, enemy.y), 5))
        return ally_hp >= enemy.hp + 40
