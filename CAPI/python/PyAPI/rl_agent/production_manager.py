from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.interaction_contract import InteractionContext, can_produce
from PyAPI.rl_agent.utils import accepted, now_ms

@dataclass
class GoodsRequest:
    goods_type: THUAI9.GoodsType
    min_amount: int
    requester_id: int
    timestamp_ms: int

class ProductionManager:
    def __init__(self) -> None:
        self.requests: Dict[int, GoodsRequest] = {}
        self.last_produce_ms: int = -10**12
        self.cooldown_ms: int = 2500
        self.last_goods: Optional[THUAI9.GoodsType] = None

    def update(self, ctx: InteractionContext) -> None:
        now = now_ms()
        self.requests = {k: v for k, v in self.requests.items() if now - v.timestamp_ms < 20000}

    def request_goods(self, goods_type: THUAI9.GoodsType, min_amount: int, requester_id: int) -> None:
        self.requests[requester_id] = GoodsRequest(goods_type, max(1, min_amount), requester_id, now_ms())

    def choose_goods_to_produce(self, ctx: InteractionContext) -> Optional[THUAI9.GoodsType]:
        team = ctx.team_info
        if team is None or team.material <= 0:
            return None
        factory = _team_factory(ctx)
        inv_total = sum(factory.productInventory.values()) if factory is not None else 0
        if factory is not None and inv_total >= max(2, min(factory.storage, 10)):
            return None
        if self.requests:
            req = sorted(self.requests.values(), key=lambda r: r.timestamp_ms)[0]
            if team.material >= _cost(req.goods_type):
                return req.goods_type
        if team.material >= 30:
            return THUAI9.GoodsType.Semiconductor
        if team.material >= 5:
            return THUAI9.GoodsType.Medicine
        return THUAI9.GoodsType.Toys

    def maybe_produce(self, api, ctx: InteractionContext) -> tuple[bool, str, Optional[THUAI9.GoodsType]]:
        self.update(ctx)
        now = now_ms()
        if now - self.last_produce_ms < self.cooldown_ms:
            return False, "cooldown_active", None
        goods = self.choose_goods_to_produce(ctx)
        if goods is None:
            return False, "no_production_needed", None
        amount = 1
        ok, reason = can_produce(ctx, goods, amount)
        if not ok:
            if reason in {"factory_busy", "factory_storage_full", "no_material"}:
                self.last_produce_ms = now
            return False, reason, goods
        success = accepted(api.ProduceGoods(goods, amount), timeout=0.08)
        self.last_produce_ms = now
        self.last_goods = goods
        return success, "ok" if success else "capi_return_false", goods


def _cost(goods: THUAI9.GoodsType) -> int:
    return {THUAI9.GoodsType.Semiconductor: 10, THUAI9.GoodsType.Medicine: 5, THUAI9.GoodsType.Toys: 1}.get(goods, 1)


def _team_factory(ctx: InteractionContext):
    team = ctx.team_info
    if team is None:
        return None
    game_map = ctx.api.GetFullMap()
    for x, row in enumerate(game_map or []):
        for y, place in enumerate(row):
            if place == THUAI9.PlaceType.Factory:
                fac = ctx.api.GetFactoryState(x, y)
                if fac is not None and fac.teamID == team.teamID:
                    return fac
    return None
