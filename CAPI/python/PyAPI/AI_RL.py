from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import PyAPI.structures as THUAI9
from PyAPI.AI import AI as BaselineAI
from PyAPI.AI import Setting
from PyAPI.Interface import ICharacterAPI, ITeamAPI


StateKey = Tuple[str, ...]
ActionName = str


class QLearner:
    def __init__(self, name: str, actions: List[ActionName]):
        self.actions = actions
        self.alpha = float(os.getenv("THUAI9_RL_ALPHA", "0.25"))
        self.gamma = float(os.getenv("THUAI9_RL_GAMMA", "0.90"))
        self.epsilon = float(os.getenv("THUAI9_RL_EPSILON", "0.08"))
        self.training = os.getenv("THUAI9_RL_TRAIN", "1") != "0"
        self.path = Path(__file__).with_name(f"{name}.json")
        self.q: Dict[str, Dict[str, float]] = {}
        self._load()

    def choose(self, state: StateKey, preferred: Optional[ActionName] = None) -> ActionName:
        state_id = self._state_id(state)
        values = self.q.setdefault(state_id, {})
        for action in self.actions:
            values.setdefault(action, 0.0)

        if self.training and random.random() < self.epsilon:
            return random.choice(self.actions)

        ranked = sorted(
            self.actions,
            key=lambda action: (values.get(action, 0.0), action == preferred),
            reverse=True,
        )
        return ranked[0]

    def update(
        self,
        state: Optional[StateKey],
        action: Optional[ActionName],
        reward: float,
        next_state: StateKey,
    ) -> None:
        if not self.training or state is None or action is None:
            return

        state_id = self._state_id(state)
        next_state_id = self._state_id(next_state)
        values = self.q.setdefault(state_id, {})
        next_values = self.q.setdefault(next_state_id, {})
        old_value = values.get(action, 0.0)
        next_best = max((next_values.get(next_action, 0.0) for next_action in self.actions), default=0.0)
        values[action] = old_value + self.alpha * (reward + self.gamma * next_best - old_value)

    def save(self) -> None:
        if not self.training:
            return
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self.q, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.path)

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(raw, dict):
            loaded: Dict[str, Dict[str, float]] = {}
            for state, actions in raw.items():
                if not isinstance(actions, dict):
                    continue
                loaded[str(state)] = {
                    str(action): float(value)
                    for action, value in actions.items()
                }
            self.q = loaded

    def _state_id(self, state: StateKey) -> str:
        return "|".join(state)


class AI(BaselineAI):
    CHARACTER_ACTIONS = [
        "attack",
        "sell",
        "load",
        "occupy",
        "harvest",
        "go_market",
        "go_center",
        "go_resource",
        "go_factory",
        "baseline",
    ]
    TEAM_ACTIONS = [
        "build",
        "produce_expensive",
        "produce_mid",
        "produce_cheap",
        "tech_economy",
        "tech_mobility",
        "baseline",
    ]

    def __init__(self, playerID: int):
        super().__init__(playerID)
        self._character_learner = QLearner(
            f"rl_character_qtable_p{playerID}",
            self.CHARACTER_ACTIONS,
        )
        self._team_learner = QLearner("rl_team_qtable", self.TEAM_ACTIONS)
        self._last_character_state: Optional[StateKey] = None
        self._last_character_action: Optional[ActionName] = None
        self._last_character_value: Optional[Tuple[int, int, int, int]] = None
        self._last_team_state: Optional[StateKey] = None
        self._last_team_action: Optional[ActionName] = None
        self._last_team_value: Optional[Tuple[int, int, int, int]] = None

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
        state = self._character_state(api, self_info, game_map)
        value = self._character_value(api, self_info)
        reward = self._character_reward(value)
        self._character_learner.update(
            self._last_character_state,
            self._last_character_action,
            reward,
            state,
        )

        if frame > 0 and frame % 200 == 0:
            self._character_learner.save()

        if self_info.characterActiveState not in (
            THUAI9.CharacterState.Idle,
            THUAI9.CharacterState.NoneState,
        ):
            self._remember_character(state, None, value)
            return

        preferred = self._preferred_character_action(api, self_info, game_map)
        action = self._character_learner.choose(state, preferred)
        if not self._run_character_action(action, api, self_info, game_map, frame):
            super().CharacterPlay(api)
            action = "baseline"

        self._remember_character(state, action, value)

    def TeamPlay(self, api: ITeamAPI) -> None:
        team_info = api.GetSelfInfo()
        if team_info is None:
            return

        frame = api.GetFrameCount()
        state = self._team_state(api, team_info)
        value = self._team_value(api, team_info)
        reward = self._team_reward(value)
        self._team_learner.update(
            self._last_team_state,
            self._last_team_action,
            reward,
            state,
        )

        if frame > 0 and frame % 200 == 0:
            self._team_learner.save()

        if frame - self._last_team_command_frame < 12:
            self._remember_team(state, None, value)
            return

        preferred = self._preferred_team_action(api, team_info)
        action = self._team_learner.choose(state, preferred)
        if not self._run_team_action(action, api, team_info, frame):
            super().TeamPlay(api)
            action = "baseline"

        self._remember_team(state, action, value)

    def _character_state(
        self,
        api: ICharacterAPI,
        self_info: THUAI9.Character,
        game_map: List[List[THUAI9.PlaceType]],
    ) -> StateKey:
        self_cell = self._cell_of_grid(self_info.x, self_info.y)
        own_factory = self._own_factory(api, self_info.teamID, self_cell)
        market = self._best_market(api, self_cell)
        center = self._target_compute_center(api, self_cell, self_info.teamID)
        resource = self._target_resource(api, self_cell)
        enemy = self._nearest_attack_target(api, self_info, game_map)

        return (
            f"type:{int(self_info.characterType)}",
            f"hp:{self._bucket(self_info.hp, (30, 80, 130))}",
            f"load:{self._bucket(self_info.currentLoad, (1, self_info.carryCapacity))}",
            f"goods:{int(self._total_goods(self_info) > 0)}",
            f"enemy:{int(enemy is not None)}",
            f"factory:{int(own_factory is not None and self._near(self_cell, own_factory))}",
            f"market:{int(market is not None and self._near(self_cell, market))}",
            f"center:{int(center is not None and self._near(self_cell, center))}",
            f"resource:{int(resource is not None and self._near(self_cell, resource))}",
        )

    def _team_state(self, api: ITeamAPI, team_info: THUAI9.Team) -> StateKey:
        characters = api.GetCharacters()
        return (
            f"chars:{len(characters)}",
            f"material:{self._bucket(team_info.material, (1, 5, 10, 30))}",
            f"compute:{self._bucket(team_info.computePower, (40, 50, 80, 120))}",
            f"score:{self._bucket(team_info.score, (100, 500, 1500, 5000))}",
            f"hp:{self._bucket(team_info.factoryHP, (40, 80, 150, 250))}",
        )

    def _preferred_character_action(
        self,
        api: ICharacterAPI,
        self_info: THUAI9.Character,
        game_map: List[List[THUAI9.PlaceType]],
    ) -> ActionName:
        self_cell = self._cell_of_grid(self_info.x, self_info.y)
        if self._nearest_attack_target(api, self_info, game_map) is not None:
            return "attack"
        if self._total_goods(self_info) > 0:
            market = self._best_market(api, self_cell)
            return "sell" if market is not None and self._near(self_cell, market) else "go_market"
        own_factory = self._own_factory(api, self_info.teamID, self_cell)
        if own_factory is not None and self._near(self_cell, own_factory):
            return "load"
        if self_info.characterType in (THUAI9.CharacterType.Drone, THUAI9.CharacterType.Robot):
            center = self._target_compute_center(api, self_cell, self_info.teamID)
            if center is not None:
                return "occupy" if self._near(self_cell, center) else "go_center"
        resource = self._target_resource(api, self_cell)
        if resource is not None:
            return "harvest" if self._near(self_cell, resource) else "go_resource"
        return "baseline"

    def _preferred_team_action(self, api: ITeamAPI, team_info: THUAI9.Team) -> ActionName:
        if len(api.GetCharacters()) < 3 and team_info.computePower >= 50:
            return "build"
        if team_info.material >= 10:
            return "produce_expensive"
        if team_info.material >= 5:
            return "produce_mid"
        if team_info.material >= 1:
            return "produce_cheap"
        if team_info.computePower >= 40:
            return "tech_economy"
        return "baseline"

    def _run_character_action(
        self,
        action: ActionName,
        api: ICharacterAPI,
        self_info: THUAI9.Character,
        game_map: List[List[THUAI9.PlaceType]],
        frame: int,
    ) -> bool:
        self_cell = self._cell_of_grid(self_info.x, self_info.y)
        if action == "attack":
            target = self._nearest_attack_target(api, self_info, game_map)
            if target is None:
                return False
            api.Common_Attack(target.playerID)
            return True
        if action == "sell":
            if self._total_goods(self_info) <= 0:
                return False
            self._sell_loaded_goods(api, self_info)
            return True
        if action == "load":
            return self._try_load_goods(api, self_info)
        if action == "occupy":
            center = self._target_compute_center(api, self_cell, self_info.teamID)
            if center is None or not self._near(self_cell, center):
                return False
            api.Occupy()
            return True
        if action == "harvest":
            resource = self._target_resource(api, self_cell)
            if resource is None or not self._near(self_cell, resource):
                return False
            api.Harvest()
            return True
        if action == "go_market":
            return self._move_to_target(api, game_map, self_info, self._best_market(api, self_cell), frame)
        if action == "go_center":
            return self._move_to_target(
                api,
                game_map,
                self_info,
                self._target_compute_center(api, self_cell, self_info.teamID),
                frame,
            )
        if action == "go_resource":
            return self._move_to_target(api, game_map, self_info, self._target_resource(api, self_cell), frame)
        if action == "go_factory":
            return self._move_to_target(
                api,
                game_map,
                self_info,
                self._own_factory(api, self_info.teamID, self_cell),
                frame,
            )
        return False

    def _run_team_action(
        self,
        action: ActionName,
        api: ITeamAPI,
        team_info: THUAI9.Team,
        frame: int,
    ) -> bool:
        if action == "build":
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
                    return True
            return False
        if action == "produce_expensive" and team_info.material >= 10:
            api.ProduceGoods(THUAI9.GoodsType.Semiconductor, max(1, team_info.material // 10))
        elif action == "produce_mid" and team_info.material >= 5:
            api.ProduceGoods(THUAI9.GoodsType.Medicine, max(1, team_info.material // 5))
        elif action == "produce_cheap" and team_info.material >= 1:
            api.ProduceGoods(THUAI9.GoodsType.Toys, team_info.material)
        elif action == "tech_economy" and team_info.computePower >= 40:
            api.UplevelTech(THUAI9.TechType.IncreaseEfficiency)
        elif action == "tech_mobility" and team_info.computePower >= 40:
            api.UplevelTech(THUAI9.TechType.IncreaseMoveSpeed)
        else:
            return False
        self._last_team_command_frame = frame
        return True

    def _move_to_target(
        self,
        api: ICharacterAPI,
        game_map: List[List[THUAI9.PlaceType]],
        self_info: THUAI9.Character,
        target: Optional[Tuple[int, int]],
        frame: int,
    ) -> bool:
        if target is None:
            return False
        self._move_towards_interaction(api, game_map, self_info, target, frame)
        return True

    def _character_value(
        self,
        api: ICharacterAPI,
        self_info: THUAI9.Character,
    ) -> Tuple[int, int, int, int]:
        return (
            api.GetScore(),
            api.GetMaterial(),
            api.GetComputingPower(),
            self_info.hp + self_info.currentLoad * 8 + self._total_goods(self_info) * 20,
        )

    def _team_value(self, api: ITeamAPI, team_info: THUAI9.Team) -> Tuple[int, int, int, int]:
        return (
            team_info.score,
            team_info.material,
            team_info.computePower,
            team_info.factoryHP + len(api.GetCharacters()) * 100,
        )

    def _character_reward(self, value: Tuple[int, int, int, int]) -> float:
        if self._last_character_value is None:
            return 0.0
        return self._delta_reward(self._last_character_value, value)

    def _team_reward(self, value: Tuple[int, int, int, int]) -> float:
        if self._last_team_value is None:
            return 0.0
        return self._delta_reward(self._last_team_value, value)

    def _delta_reward(self, old: Tuple[int, int, int, int], new: Tuple[int, int, int, int]) -> float:
        score_delta = new[0] - old[0]
        material_delta = new[1] - old[1]
        compute_delta = new[2] - old[2]
        survival_delta = new[3] - old[3]
        return score_delta * 0.02 + material_delta * 0.4 + compute_delta * 0.1 + survival_delta * 0.05

    def _remember_character(
        self,
        state: StateKey,
        action: Optional[ActionName],
        value: Tuple[int, int, int, int],
    ) -> None:
        self._last_character_state = state
        self._last_character_action = action
        self._last_character_value = value

    def _remember_team(
        self,
        state: StateKey,
        action: Optional[ActionName],
        value: Tuple[int, int, int, int],
    ) -> None:
        self._last_team_state = state
        self._last_team_action = action
        self._last_team_value = value

    def _bucket(self, value: int, cuts: Tuple[int, ...]) -> int:
        for index, cut in enumerate(cuts):
            if value < cut:
                return index
        return len(cuts)
