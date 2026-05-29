from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.utils import Cell, cell_of, goods_total, near

REASON_OK = "ok"

@dataclass
class InteractionContext:
    api: object
    self_info: Optional[THUAI9.Character] = None
    team_info: Optional[THUAI9.Team] = None
    origin: Optional[Cell] = None
    target_resource: Optional[Cell] = None
    target_factory: Optional[Cell] = None
    target_market: Optional[Cell] = None
    target_center: Optional[Cell] = None
    max_characters: int = 6

    @classmethod
    def character(cls, api, self_info: THUAI9.Character, nav) -> "InteractionContext":
        origin = cell_of(self_info.x, self_info.y)
        return cls(
            api=api,
            self_info=self_info,
            origin=origin,
            target_resource=nav.nearest_resource(api, origin),
            target_factory=nav.own_factory(api, origin, self_info.teamID),
            target_market=nav.nearest_market(api, origin),
            target_center=nav.nearest_center(api, origin, self_info.teamID),
        )

    @classmethod
    def team(cls, api, team_info: THUAI9.Team, nav, max_characters: int = 6) -> "InteractionContext":
        return cls(api=api, team_info=team_info, max_characters=max_characters)


def _char_ready(ctx: InteractionContext) -> Tuple[bool, str]:
    ch = ctx.self_info
    if ch is None:
        return False, "unknown_api_state"
    if ch.characterActiveState == THUAI9.CharacterState.Deceased:
        return False, "character_dead"
    if ch.characterActiveState not in (THUAI9.CharacterState.Idle, THUAI9.CharacterState.NoneState):
        return False, "character_busy"
    return True, REASON_OK


def can_harvest(ctx: InteractionContext) -> tuple[bool, str]:
    ok, reason = _char_ready(ctx)
    if not ok:
        return ok, reason
    ch = ctx.self_info
    assert ch is not None
    if ctx.target_resource is None:
        return False, "no_resource_nearby"
    if not near(ctx.origin or cell_of(ch.x, ch.y), ctx.target_resource):
        return False, "not_in_interaction_range"
    state = ctx.api.GetResourceState(*ctx.target_resource)
    if state is None:
        return False, "unknown_api_state"
    if state.state == THUAI9.ResourceState.Harvested:
        return False, "resource_depleted"
    return True, REASON_OK


def can_produce(ctx: InteractionContext, goods_type: THUAI9.GoodsType, amount: int) -> tuple[bool, str]:
    team = ctx.team_info
    if team is None:
        return False, "unknown_api_state"
    if amount <= 0:
        return False, "amount_zero"
    cost = _goods_cost(goods_type) * amount
    if team.material < cost:
        return False, "no_material"
    factory = _team_factory(ctx.api, team.teamID)
    if factory is None:
        return False, "no_factory_nearby"
    if not factory.canProduce:
        return False, "factory_busy"
    if sum(factory.productInventory.values()) >= factory.storage:
        return False, "factory_storage_full"
    return True, REASON_OK


def can_load(ctx: InteractionContext, goods_type: THUAI9.GoodsType, amount: int) -> tuple[bool, str]:
    ok, reason = _char_ready(ctx)
    if not ok:
        return ok, reason
    ch = ctx.self_info
    assert ch is not None
    if amount <= 0:
        return False, "amount_zero"
    if ctx.target_factory is None:
        return False, "no_factory_nearby"
    if not near(ctx.origin or cell_of(ch.x, ch.y), ctx.target_factory):
        return False, "not_in_interaction_range"
    room = ch.carryCapacity - ch.currentLoad
    if room <= 0:
        return False, "capacity_full"
    factory = ctx.api.GetFactoryState(*ctx.target_factory)
    if factory is None:
        return False, "unknown_api_state"
    inv = int(factory.productInventory.get(goods_type, 0))
    if inv <= 0:
        return False, "no_product_inventory"
    if amount > inv:
        return False, "amount_exceeds_inventory"
    if amount > room:
        return False, "amount_exceeds_capacity"
    return True, REASON_OK


def can_sell(ctx: InteractionContext, goods_type: THUAI9.GoodsType, amount: int) -> tuple[bool, str]:
    ok, reason = _char_ready(ctx)
    if not ok:
        return ok, reason
    ch = ctx.self_info
    assert ch is not None
    if amount <= 0:
        return False, "amount_zero"
    if ctx.target_market is None:
        return False, "no_market_nearby"
    if not near(ctx.origin or cell_of(ch.x, ch.y), ctx.target_market):
        return False, "not_in_interaction_range"
    have = int(ch.goodsLoad.get(goods_type, 0))
    if have <= 0:
        return False, "no_goods_carried"
    if amount > have:
        return False, "amount_exceeds_carried"
    return True, REASON_OK


def can_occupy(ctx: InteractionContext) -> tuple[bool, str]:
    ok, reason = _char_ready(ctx)
    if not ok:
        return ok, reason
    ch = ctx.self_info
    assert ch is not None
    if ch.characterType not in (THUAI9.CharacterType.Drone, THUAI9.CharacterType.Robot):
        return False, "wrong_character_type"
    if ctx.target_center is None:
        return False, "no_compute_center_nearby"
    if not near(ctx.origin or cell_of(ch.x, ch.y), ctx.target_center):
        return False, "not_in_interaction_range"
    return True, REASON_OK


def can_build_character(ctx: InteractionContext, character_type: THUAI9.CharacterType, player_id: int) -> tuple[bool, str]:
    team = ctx.team_info
    if team is None:
        return False, "unknown_api_state"
    if player_id <= 0:
        return False, "invalid_player_id"
    chars = [c for c in ctx.api.GetCharacters() if c.characterActiveState != THUAI9.CharacterState.Deceased]
    if len(chars) >= ctx.max_characters:
        return False, "team_character_limit"
    if any(c.playerID == player_id for c in chars):
        return False, "player_id_exists"
    if team.computePower < 50:
        return False, "compute_not_enough"
    factory = _team_factory(ctx.api, team.teamID)
    if factory is not None and not factory.canRecruit:
        return False, "factory_not_ready"
    return True, REASON_OK


def can_upgrade_tech(ctx: InteractionContext, tech_type: THUAI9.TechType) -> tuple[bool, str]:
    team = ctx.team_info
    if team is None:
        return False, "unknown_api_state"
    if team.computePower < 40:
        return False, "compute_not_enough"
    return True, REASON_OK


def can_attack(ctx: InteractionContext, target_id: int) -> tuple[bool, str]:
    ok, reason = _char_ready(ctx)
    if not ok:
        return ok, reason
    ch = ctx.self_info
    assert ch is not None
    for enemy in ctx.api.GetEnemyCharacters():
        if enemy.playerID == target_id and enemy.characterActiveState != THUAI9.CharacterState.Deceased:
            if (ch.x - enemy.x) ** 2 + (ch.y - enemy.y) ** 2 <= ch.commonAttackRange ** 2:
                return True, REASON_OK
            return False, "not_in_interaction_range"
    return False, "target_not_visible"


def _team_factory(api, team_id: int):
    game_map = api.GetFullMap()
    for x, row in enumerate(game_map or []):
        for y, place in enumerate(row):
            if place == THUAI9.PlaceType.Factory:
                fac = api.GetFactoryState(x, y)
                if fac is not None and fac.teamID == team_id:
                    return fac
    return None


def _goods_cost(goods_type: THUAI9.GoodsType) -> int:
    return {
        THUAI9.GoodsType.Semiconductor: 10,
        THUAI9.GoodsType.Medicine: 5,
        THUAI9.GoodsType.Toys: 1,
        THUAI9.GoodsType.Clothes: 1,
        THUAI9.GoodsType.Food: 1,
    }.get(goods_type, 1)
