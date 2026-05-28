from __future__ import annotations

from pathlib import Path

TEMPLATE = """agent_mode: {mode}
decision_interval_ms: 300
log_path: outputs/rl_pvp/logs
checkpoint_path: outputs/rl_pvp/checkpoints/policy.pt
server_port: 8888
team_count: {team_count}
game_duration: {duration}
reward_weights:
  delta_score: 0.02
  delta_inventory_value: 0.03
  delta_compute_power: 0.05
  invalid_action_penalty: -0.4
  terminal_win_bonus: 25.0
opponent_sampling:
  rule: 0.5
  random: 0.2
  historical: 0.3
evaluation_seeds: [0, 1, 2, 3, 4]
"""


def main() -> None:
    out = Path("configs/rl_pvp")
    out.mkdir(parents=True, exist_ok=True)
    specs = {
        "rule_baseline.yaml": ("rule", 2, 120),
        "ppo.yaml": ("policy", 2, 300),
        "mappo.yaml": ("policy", 4, 300),
        "eval_1v1.yaml": ("rule", 2, 180),
        "eval_4team.yaml": ("rule", 4, 180),
    }
    for name, (mode, team_count, duration) in specs.items():
        (out / name).write_text(TEMPLATE.format(mode=mode, team_count=team_count, duration=duration), encoding="utf-8")


if __name__ == "__main__":
    main()
