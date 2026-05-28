from __future__ import annotations

import traceback
from typing import Optional

from PyAPI.Interface import IAI, ICharacterAPI, ITeamAPI
from PyAPI.rl_agent import build_agent
from PyAPI.rl_agent.agent import BaseTHUAI9Agent
from PyAPI.rl_agent.config import load_config


class Setting:
    @staticmethod
    def Asynchronous() -> bool:
        return False


class AI(IAI):
    """Official PyAPI entrypoint; real logic lives in PyAPI.rl_agent."""

    def __init__(self, playerID: int):
        self.playerID = playerID
        self._agent: Optional[BaseTHUAI9Agent] = None
        self._agent_kind: Optional[str] = None

    def CharacterPlay(self, api: ICharacterAPI) -> None:
        self._safe_step(api, "character")

    def TeamPlay(self, api: ITeamAPI) -> None:
        self._safe_step(api, "team")

    def _safe_step(self, api, kind: str) -> None:
        try:
            if self._agent is None or self._agent_kind != kind:
                config = load_config()
                self._agent = build_agent(api, self.playerID, config)
                self._agent_kind = kind
            self._agent.step(api)
        except Exception:
            try:
                api.Print("[rl_agent] step exception:\n" + traceback.format_exc())
            except Exception:
                pass
