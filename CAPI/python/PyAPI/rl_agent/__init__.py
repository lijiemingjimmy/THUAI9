from __future__ import annotations

from PyAPI.rl_agent.agent import BaseTHUAI9Agent
from PyAPI.rl_agent.config import AgentConfig


def build_agent(api, player_id: int, config: AgentConfig) -> BaseTHUAI9Agent:
    mode = config.agent_mode.lower()
    if mode == "policy":
        from PyAPI.rl_agent.policy_agent import PolicyAgent

        return PolicyAgent(api, player_id, config)
    if mode in {"random", "debug"}:
        from PyAPI.rl_agent.rule_agent import RandomAgent

        return RandomAgent(api, player_id, config)
    from PyAPI.rl_agent.rule_agent import RuleAgent

    return RuleAgent(api, player_id, config)


__all__ = ["AgentConfig", "BaseTHUAI9Agent", "build_agent"]
