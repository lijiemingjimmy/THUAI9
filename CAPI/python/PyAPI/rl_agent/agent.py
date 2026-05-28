from __future__ import annotations

from abc import ABC, abstractmethod

from PyAPI.rl_agent.config import AgentConfig
from PyAPI.rl_agent.logger import RolloutLogger
from PyAPI.rl_agent.macro_actions import MacroExecutor
from PyAPI.rl_agent.navigation import Navigator
from PyAPI.rl_agent.state_tracker import GLOBAL_TRACKER, StateTracker


class BaseTHUAI9Agent(ABC):
    def __init__(self, api, player_id: int, config: AgentConfig):
        self.api = api
        self.player_id = player_id
        self.config = config
        self.navigator = Navigator()
        self.tracker: StateTracker = GLOBAL_TRACKER
        self.executor = MacroExecutor(self.navigator, self.tracker, config.move_time_ms)
        self._log_team_id = config.team_id or 0
        self.logger = RolloutLogger(config, self._log_team_id, player_id)

    def ensure_logger_team(self, team_id: int) -> None:
        if team_id and team_id != self._log_team_id:
            self._log_team_id = team_id
            self.logger = RolloutLogger(self.config, team_id, self.player_id)

    @abstractmethod
    def step(self, api=None) -> None:
        raise NotImplementedError

    def reset_local_state(self) -> None:
        self.tracker.players.pop(self.player_id, None)
