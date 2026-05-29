from __future__ import annotations

from enum import IntEnum
from typing import Dict, List, Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.navigation import Navigator
from PyAPI.rl_agent.utils import cell_of, goods_total, near


class TeamAction(IntEnum):
    RECRUIT_CAR = 0
    RECRUIT_DRONE = 1
    RECRUIT_ROBOT = 2
    PRODUCE_SEMICONDUCTOR = 3
    PRODUCE_MEDICINE = 4
    PRODUCE_TOYS = 5
    UPGRADE_EFFICIENCY = 6
    UPGRADE_MOVE_SPEED = 7
    UPGRADE_ATTACK = 8
    SAVE_COMPUTE = 9
    IDLE = 10


class CharacterAction(IntEnum):
    GO_RESOURCE = 0
    GO_MARKET = 1
    GO_CENTER = 2
    GO_FACTORY = 3
    GO_ENEMY = 4
    HARVEST = 5
    OCCUPY_CENTER = 6
    LOAD_GOODS = 7
    SELL_GOODS = 8
    ATTACK_NEAREST_ENEMY = 9
    PRESSURE_ENEMY_FACTORY = 10
    RETREAT = 11
    IDLE = 12


TEAM_ACTIONS = list(TeamAction)
CHARACTER_ACTIONS = list(CharacterAction)
ACTION_SPACE_VERSION = "stage4_v1"


def team_action_mask(api, team_info: THUAI9.Team, max_characters: int = 6) -> Dict[TeamAction, bool]:
    chars = [c for c in api.GetCharacters() if c.characterActiveState != THUAI9.CharacterState.Deceased]
    has_slot = len(chars) < max_characters
    can_build = team_info.computePower >= 50 and has_slot
    factory = _team_factory(api, team_info.teamID)
    can_produce = bool(factory is not None and factory.canProduce and sum(factory.productInventory.values()) < factory.storage)
    return {
        TeamAction.RECRUIT_CAR: can_build,
        TeamAction.RECRUIT_DRONE: can_build,
        TeamAction.RECRUIT_ROBOT: can_build,
        TeamAction.PRODUCE_SEMICONDUCTOR: can_produce and team_info.material >= 10,
        TeamAction.PRODUCE_MEDICINE: can_produce and team_info.material >= 5,
        TeamAction.PRODUCE_TOYS: can_produce and team_info.material >= 1,
        TeamAction.UPGRADE_EFFICIENCY: team_info.computePower >= 40,
        TeamAction.UPGRADE_MOVE_SPEED: team_info.computePower >= 40,
        TeamAction.UPGRADE_ATTACK: team_info.computePower >= 40,
        TeamAction.SAVE_COMPUTE: True,
        TeamAction.IDLE: True,
    }


def character_action_mask(api, self_info: Optional[THUAI9.Character], nav: Navigator, game_map) -> Dict[CharacterAction, bool]:
    mask = {a: False for a in CharacterAction}
    mask[CharacterAction.IDLE] = True
    if self_info is None or self_info.characterActiveState == THUAI9.CharacterState.Deceased:
        return mask
    origin = cell_of(self_info.x, self_info.y)
    has_goods = goods_total(self_info.goodsLoad) > 0
    room = self_info.currentLoad < self_info.carryCapacity
    own_factory = nav.own_factory(api, origin, self_info.teamID)
    market = nav.nearest_market(api, origin)
    resource = nav.nearest_resource(api, origin)
    center = nav.nearest_center(api, origin, self_info.teamID)
    enemy_factory = nav.enemy_factory(api, origin, self_info.teamID)
    visible_enemies = [e for e in api.GetEnemyCharacters() if e.characterActiveState != THUAI9.CharacterState.Deceased]
    attackable = any((self_info.x - e.x) ** 2 + (self_info.y - e.y) ** 2 <= self_info.commonAttackRange ** 2 for e in visible_enemies)

    mask[CharacterAction.GO_RESOURCE] = resource is not None
    mask[CharacterAction.HARVEST] = resource is not None and near(origin, resource)
    mask[CharacterAction.GO_CENTER] = center is not None
    mask[CharacterAction.OCCUPY_CENTER] = center is not None and near(origin, center) and self_info.characterType in (THUAI9.CharacterType.Drone, THUAI9.CharacterType.Robot)
    mask[CharacterAction.GO_MARKET] = market is not None and has_goods
    mask[CharacterAction.SELL_GOODS] = market is not None and has_goods and near(origin, market)
    mask[CharacterAction.GO_FACTORY] = own_factory is not None
    has_factory_goods = False
    if own_factory is not None:
        fac = api.GetFactoryState(*own_factory)
        has_factory_goods = fac is not None and any(int(v) > 0 for v in fac.productInventory.values())
    mask[CharacterAction.LOAD_GOODS] = own_factory is not None and room and near(origin, own_factory) and has_factory_goods
    mask[CharacterAction.GO_ENEMY] = bool(visible_enemies)
    mask[CharacterAction.ATTACK_NEAREST_ENEMY] = attackable
    mask[CharacterAction.PRESSURE_ENEMY_FACTORY] = enemy_factory is not None
    mask[CharacterAction.RETREAT] = own_factory is not None and self_info.hp > 0
    return mask


def mask_as_list(mask: Dict[IntEnum, bool], actions: List[IntEnum]) -> List[int]:
    return [1 if mask.get(action, False) else 0 for action in actions]


def _team_factory(api, team_id: int):
    game_map = api.GetFullMap()
    for x, row in enumerate(game_map or []):
        for y, place in enumerate(row):
            if place == THUAI9.PlaceType.Factory:
                fac = api.GetFactoryState(x, y)
                if fac is not None and fac.teamID == team_id:
                    return fac
    return None
