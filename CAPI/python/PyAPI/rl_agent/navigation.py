from __future__ import annotations

import heapq
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import PyAPI.structures as THUAI9
from PyAPI.rl_agent.utils import Cell, PASSABLE, grid_center, iter_cells, manhattan, near


class MapCache:
    def __init__(self) -> None:
        self.ready = False
        self.resources: List[Cell] = []
        self.centers: List[Cell] = []
        self.markets: List[Cell] = []
        self.factories: List[Cell] = []
        self.walls: set[Cell] = set()

    def update(self, game_map: list[list[THUAI9.PlaceType]]) -> None:
        if self.ready or not game_map:
            return
        for cell, place in iter_cells(game_map):
            if place == THUAI9.PlaceType.Resource:
                self.resources.append(cell)
            elif place == THUAI9.PlaceType.ComputeCenter:
                self.centers.append(cell)
            elif place == THUAI9.PlaceType.Market:
                self.markets.append(cell)
            elif place == THUAI9.PlaceType.Factory:
                self.factories.append(cell)
            elif place == THUAI9.PlaceType.Barrier:
                self.walls.add(cell)
        self.ready = True


class Navigator:
    def __init__(self) -> None:
        self.cache = MapCache()

    def update(self, game_map: list[list[THUAI9.PlaceType]]) -> None:
        self.cache.update(game_map)

    def nearest_resource(self, api, origin: Cell, avoid: set[Cell] | None = None) -> Optional[Cell]:
        avoid = avoid or set()
        candidates = []
        for cell in self.cache.resources:
            state = api.GetResourceState(*cell)
            if state is None or state.state == THUAI9.ResourceState.Harvested:
                continue
            priority = -int(state.resourceType)
            penalty = 4 if cell in avoid else 0
            candidates.append((manhattan(origin, cell) + penalty, priority, cell))
        return min(candidates)[2] if candidates else None

    def nearest_center(self, api, origin: Cell, team_id: int, avoid: set[Cell] | None = None) -> Optional[Cell]:
        avoid = avoid or set()
        candidates = []
        for cell in self.cache.centers:
            state = api.GetComputeCenterState(*cell)
            if state is None:
                continue
            if state.state == THUAI9.ComputeCenterState.Occupied and state.ownerTeamID == team_id:
                continue
            candidates.append((manhattan(origin, cell) + (5 if cell in avoid else 0), cell))
        return min(candidates)[1] if candidates else None

    def nearest_market(self, api, origin: Cell, cursor: int = 0) -> Optional[Cell]:
        markets = []
        for idx, cell in enumerate(self.cache.markets):
            market = api.GetMarketState(*cell)
            if market is None:
                continue
            rank = -int(market.marketType)
            rotate = 0 if idx % max(1, len(self.cache.markets)) == cursor % max(1, len(self.cache.markets)) else 1
            markets.append((manhattan(origin, cell), rotate, rank, cell))
        return min(markets)[3] if markets else None

    def own_factory(self, api, origin: Cell, team_id: int) -> Optional[Cell]:
        factories = []
        for cell in self.cache.factories:
            factory = api.GetFactoryState(*cell)
            if factory is not None and factory.teamID == team_id:
                factories.append((manhattan(origin, cell), cell))
        if factories:
            return min(factories)[1]
        return min(self.cache.factories, key=lambda c: manhattan(origin, c), default=None)

    def enemy_factory(self, api, origin: Cell, team_id: int) -> Optional[Cell]:
        factories = []
        for cell in self.cache.factories:
            factory = api.GetFactoryState(*cell)
            if factory is not None and factory.teamID not in (0, team_id):
                factories.append((manhattan(origin, cell), cell))
        return min(factories)[1] if factories else None

    def retreat_point(self, api, origin: Cell, team_id: int) -> Optional[Cell]:
        return self.own_factory(api, origin, team_id)

    def next_step(self, game_map: list[list[THUAI9.PlaceType]], origin: Cell, target: Cell) -> Optional[Cell]:
        goal = self.nearest_interaction_cell(game_map, origin, target) or target
        if origin == goal:
            return None
        if not self._passable(game_map, origin) or not self._in_map(game_map, goal):
            return None
        frontier = [(0, origin)]
        came_from: Dict[Cell, Optional[Cell]] = {origin: None}
        cost: Dict[Cell, int] = {origin: 0}
        while frontier:
            _, current = heapq.heappop(frontier)
            if current == goal:
                break
            for nxt in self._neighbors(game_map, current):
                new_cost = cost[current] + 1
                if new_cost >= cost.get(nxt, 10**9):
                    continue
                cost[nxt] = new_cost
                heapq.heappush(frontier, (new_cost + manhattan(nxt, goal), nxt))
                came_from[nxt] = current
        if goal not in came_from:
            return None
        cur = goal
        while came_from[cur] is not None and came_from[cur] != origin:
            cur = came_from[cur]  # type: ignore[index]
        return cur

    def nearest_interaction_cell(self, game_map: list[list[THUAI9.PlaceType]], origin: Cell, target: Cell) -> Optional[Cell]:
        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = (target[0] + dx, target[1] + dy)
                if cell == target or not self._passable(game_map, cell):
                    continue
                candidates.append((manhattan(origin, cell), cell))
        return min(candidates)[1] if candidates else None

    def _neighbors(self, game_map: list[list[THUAI9.PlaceType]], cell: Cell) -> Sequence[Cell]:
        x, y = cell
        return [c for c in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)) if self._passable(game_map, c)]

    def _passable(self, game_map: list[list[THUAI9.PlaceType]], cell: Cell) -> bool:
        return self._in_map(game_map, cell) and game_map[cell[0]][cell[1]] in PASSABLE

    def _in_map(self, game_map: list[list[THUAI9.PlaceType]], cell: Cell) -> bool:
        return bool(game_map) and 0 <= cell[0] < len(game_map) and 0 <= cell[1] < len(game_map[0])
