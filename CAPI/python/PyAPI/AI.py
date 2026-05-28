from __future__ import annotations

import heapq
import math
from typing import Dict, List, Optional, Sequence, Tuple

import PyAPI.structures as THUAI9
from PyAPI.Interface import IAI, ICharacterAPI, ITeamAPI


Cell = Tuple[int, int]

CELL_SIZE = 1000
INTERACT_RANGE = 1
MOVE_TIME_MS = 150
PASSABLE = {THUAI9.PlaceType.Space, THUAI9.PlaceType.Bush}


class Setting:
    @staticmethod
    def Asynchronous() -> bool:
        return False


class AI(IAI):
    def __init__(self, playerID: int):
        self.playerID = playerID
        self._resource_cells: List[Cell] = []
        self._center_cells: List[Cell] = []
        self._market_cells: List[Cell] = []
        self._factory_cells: List[Cell] = []
        self._map_ready = False
        self._last_move_frame = -100
        self._last_team_command_frame = -100
        self._tech_cursor = 0

    def CharacterPlay(self, api: ICharacterAPI) -> None:
        self_info = api.GetSelfInfo()
        if (
            self_info is None
            or self_info.characterActiveState == THUAI9.CharacterState.Deceased
        ):
            return

        game_map = api.GetFullMap()
        self._ensure_map_cache(game_map)
        frame = api.GetFrameCount()

        target = self._nearest_attack_target(api, self_info, game_map)
        if target is not None:
            api.Common_Attack(target.playerID)
            return

        if self_info.characterActiveState not in (
            THUAI9.CharacterState.Idle,
            THUAI9.CharacterState.NoneState,
        ):
            return

        self_cell = self._cell_of_grid(self_info.x, self_info.y)
        own_factory = self._own_factory(api, self_info.teamID, self_cell)

        if self._total_goods(self_info) > 0:
            market = self._best_market(api, self_cell)
            if market is not None:
                if self._near(self_cell, market):
                    self._sell_loaded_goods(api, self_info)
                else:
                    self._move_towards_interaction(api, game_map, self_info, market, frame)
                return

        if own_factory is not None and self._near(self_cell, own_factory):
            if self._try_load_goods(api, self_info):
                return

        if self_info.characterType in (THUAI9.CharacterType.Drone, THUAI9.CharacterType.Robot):
            center = self._target_compute_center(api, self_cell, self_info.teamID)
            if center is not None:
                if self._near(self_cell, center):
                    api.Occupy()
                else:
                    self._move_towards_interaction(api, game_map, self_info, center, frame)
                return

        resource = self._target_resource(api, self_cell)
        if resource is not None:
            if self._near(self_cell, resource):
                api.Harvest()
            else:
                self._move_towards_interaction(api, game_map, self_info, resource, frame)
            return

        if own_factory is not None and not self._near(self_cell, own_factory):
            self._move_towards_interaction(api, game_map, self_info, own_factory, frame)

    def TeamPlay(self, api: ITeamAPI) -> None:
        team_info = api.GetSelfInfo()
        if team_info is None:
            return

        frame = api.GetFrameCount()
        if frame - self._last_team_command_frame < 12:
            return

        characters = {character.playerID: character for character in api.GetCharacters()}
        build_order = (
            (1, THUAI9.CharacterType.Drone),
            (2, THUAI9.CharacterType.Robot),
            (3, THUAI9.CharacterType.AutonomousCar),
        )
        for player_id, character_type in build_order:
            if player_id not in characters and team_info.computePower >= 50:
                api.BuildCharacter(character_type, player_id)
                self._last_team_command_frame = frame
                return

        if team_info.material >= 10:
            api.ProduceGoods(
                THUAI9.GoodsType.Semiconductor,
                max(1, team_info.material // 10),
            )
            self._last_team_command_frame = frame
            return
        elif team_info.material >= 5:
            api.ProduceGoods(
                THUAI9.GoodsType.Medicine,
                max(1, team_info.material // 5),
            )
            self._last_team_command_frame = frame
            return
        elif team_info.material >= 1:
            api.ProduceGoods(THUAI9.GoodsType.Toys, team_info.material)
            self._last_team_command_frame = frame
            return

        tech_order = (
            THUAI9.TechType.IncreaseEfficiency,
            THUAI9.TechType.IncreaseMoveSpeed,
            THUAI9.TechType.IncreaseCarryCapacity,
            THUAI9.TechType.IncreaseProduction,
            THUAI9.TechType.DecreaseCost,
            THUAI9.TechType.IncreaseStorage,
            THUAI9.TechType.IncreasePrice,
        )
        if team_info.computePower >= 40:
            tech_type = tech_order[self._tech_cursor % len(tech_order)]
            api.UplevelTech(tech_type)
            self._tech_cursor += 1
            self._last_team_command_frame = frame

    def _ensure_map_cache(self, game_map: List[List[THUAI9.PlaceType]]) -> None:
        if self._map_ready or not game_map or not game_map[0]:
            return

        for x, row in enumerate(game_map):
            for y, place in enumerate(row):
                cell = (x, y)
                if place == THUAI9.PlaceType.Resource:
                    self._resource_cells.append(cell)
                elif place == THUAI9.PlaceType.ComputeCenter:
                    self._center_cells.append(cell)
                elif place == THUAI9.PlaceType.Market:
                    self._market_cells.append(cell)
                elif place == THUAI9.PlaceType.Factory:
                    self._factory_cells.append(cell)

        self._map_ready = True

    def _nearest_attack_target(
        self,
        api: ICharacterAPI,
        self_info: THUAI9.Character,
        game_map: List[List[THUAI9.PlaceType]],
    ) -> Optional[THUAI9.Character]:
        candidates = []
        for enemy in api.GetEnemyCharacters():
            if enemy.characterActiveState == THUAI9.CharacterState.Deceased:
                continue
            distance2 = self._distance2_grid(
                (self_info.x, self_info.y),
                (enemy.x, enemy.y),
            )
            if distance2 > self_info.commonAttackRange * self_info.commonAttackRange:
                continue
            if not api.HaveView(
                self_info.x,
                self_info.y,
                enemy.x,
                enemy.y,
                self_info.viewRange,
                game_map,
            ):
                continue
            candidates.append((enemy.hp, distance2, enemy))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][2]

    def _target_resource(self, api: ICharacterAPI, origin: Cell) -> Optional[Cell]:
        active = []
        for cell in self._resource_cells:
            state = api.GetResourceState(*cell)
            if state is None or state.state == THUAI9.ResourceState.Harvested:
                continue
            priority = (
                0
                if state.resourceType == THUAI9.ResourceType.LargeResource
                else int(state.resourceType)
            )
            active.append((self._distance_cells(origin, cell), priority, cell))
        return min(active)[2] if active else None

    def _target_compute_center(
        self, api: ICharacterAPI, origin: Cell, team_id: int
    ) -> Optional[Cell]:
        active = []
        for cell in self._center_cells:
            state = api.GetComputeCenterState(*cell)
            if state is None:
                continue
            if state.state == THUAI9.ComputeCenterState.Occupied and state.ownerTeamID == team_id:
                continue
            active.append((self._distance_cells(origin, cell), cell))
        return min(active)[1] if active else None

    def _best_market(self, api: ICharacterAPI, origin: Cell) -> Optional[Cell]:
        markets = []
        for cell in self._market_cells:
            market = api.GetMarketState(*cell)
            if market is None:
                continue
            market_rank = 0
            if market.marketType == THUAI9.MarketType.LargeMarket:
                market_rank = -2
            elif market.marketType == THUAI9.MarketType.MediumMarket:
                market_rank = -1
            markets.append((self._distance_cells(origin, cell), market_rank, cell))
        return min(markets)[2] if markets else None

    def _own_factory(self, api: ICharacterAPI, team_id: int, origin: Cell) -> Optional[Cell]:
        factories = []
        for cell in self._factory_cells:
            factory = api.GetFactoryState(*cell)
            if factory is not None and factory.teamID == team_id:
                factories.append((self._distance_cells(origin, cell), cell))
        if factories:
            return min(factories)[1]
        return min(
            self._factory_cells,
            key=lambda cell: self._distance_cells(origin, cell),
            default=None,
        )

    def _try_load_goods(self, api: ICharacterAPI, self_info: THUAI9.Character) -> bool:
        room = max(0, self_info.carryCapacity - self_info.currentLoad)
        if room <= 0:
            return False
        for goods_type in (
            THUAI9.GoodsType.Semiconductor,
            THUAI9.GoodsType.Medicine,
            THUAI9.GoodsType.Clothes,
            THUAI9.GoodsType.Toys,
            THUAI9.GoodsType.Food,
        ):
            if self._accepted(api.Load(goods_type, room)):
                return True
        return False

    def _sell_loaded_goods(self, api: ICharacterAPI, self_info: THUAI9.Character) -> None:
        for goods_type, amount in self_info.goodsLoad.items():
            if amount > 0:
                api.Sell(goods_type, amount)
                return

    def _accepted(self, future) -> bool:
        try:
            return bool(future.result(timeout=0.05))
        except Exception:
            return False

    def _move_towards_interaction(
        self,
        api: ICharacterAPI,
        game_map: List[List[THUAI9.PlaceType]],
        self_info: THUAI9.Character,
        target: Cell,
        frame: int,
    ) -> None:
        if frame - self._last_move_frame < 4:
            return

        origin = self._cell_of_grid(self_info.x, self_info.y)
        goal = self._nearest_interaction_cell(game_map, origin, target)
        if goal is None:
            return

        next_cell = self._next_step(game_map, origin, goal)
        if next_cell is None:
            next_cell = goal

        next_x, next_y = self._grid_center(next_cell)
        angle = math.atan2(next_y - self_info.y, next_x - self_info.x)
        if angle < 0:
            angle += math.tau
        api.Move(MOVE_TIME_MS, angle)
        self._last_move_frame = frame

    def _next_step(
        self, game_map: List[List[THUAI9.PlaceType]], origin: Cell, goal: Cell
    ) -> Optional[Cell]:
        if origin == goal:
            return None
        if not self._in_map(game_map, origin) or not self._in_map(game_map, goal):
            return None

        frontier = [(0, origin)]
        came_from: Dict[Cell, Optional[Cell]] = {origin: None}
        cost_so_far: Dict[Cell, int] = {origin: 0}

        while frontier:
            _, current = heapq.heappop(frontier)
            if current == goal:
                break

            for nxt in self._neighbors(game_map, current):
                new_cost = cost_so_far[current] + 1
                if nxt in cost_so_far and new_cost >= cost_so_far[nxt]:
                    continue
                cost_so_far[nxt] = new_cost
                priority = new_cost + self._distance_cells(nxt, goal)
                heapq.heappush(frontier, (priority, nxt))
                came_from[nxt] = current

        if goal not in came_from:
            return None

        current = goal
        while came_from[current] is not None and came_from[current] != origin:
            current = came_from[current]  # type: ignore[index]
        return current

    def _nearest_interaction_cell(
        self, game_map: List[List[THUAI9.PlaceType]], origin: Cell, target: Cell
    ) -> Optional[Cell]:
        candidates = []
        for dx in range(-INTERACT_RANGE, INTERACT_RANGE + 1):
            for dy in range(-INTERACT_RANGE, INTERACT_RANGE + 1):
                cell = (target[0] + dx, target[1] + dy)
                if cell == target or not self._passable(game_map, cell):
                    continue
                candidates.append((self._distance_cells(origin, cell), cell))
        return min(candidates)[1] if candidates else None

    def _neighbors(self, game_map: List[List[THUAI9.PlaceType]], cell: Cell) -> Sequence[Cell]:
        x, y = cell
        cells = ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
        return [candidate for candidate in cells if self._passable(game_map, candidate)]

    def _passable(self, game_map: List[List[THUAI9.PlaceType]], cell: Cell) -> bool:
        return self._in_map(game_map, cell) and game_map[cell[0]][cell[1]] in PASSABLE

    def _in_map(self, game_map: List[List[THUAI9.PlaceType]], cell: Cell) -> bool:
        return bool(game_map) and 0 <= cell[0] < len(game_map) and 0 <= cell[1] < len(game_map[0])

    def _near(self, a: Cell, b: Cell) -> bool:
        return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= INTERACT_RANGE

    def _cell_of_grid(self, x: int, y: int) -> Cell:
        return x // CELL_SIZE, y // CELL_SIZE

    def _grid_center(self, cell: Cell) -> Tuple[int, int]:
        return cell[0] * CELL_SIZE + CELL_SIZE // 2, cell[1] * CELL_SIZE + CELL_SIZE // 2

    def _distance_cells(self, a: Cell, b: Cell) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _distance2_grid(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return (a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1])

    def _total_goods(self, self_info: THUAI9.Character) -> int:
        return sum(amount for amount in self_info.goodsLoad.values() if amount > 0)
