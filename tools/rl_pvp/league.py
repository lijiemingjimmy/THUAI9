from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class LeagueMember:
    name: str
    mode: str
    checkpoint: str = ""
    weight: float = 1.0


@dataclass
class League:
    members: List[LeagueMember] = field(default_factory=lambda: [
        LeagueMember("rule_baseline", "rule", weight=0.35),
        LeagueMember("main", "policy", "outputs/rl_pvp/checkpoints/policy.pt", 0.35),
        LeagueMember("economy_exploiter", "policy", "outputs/rl_pvp/checkpoints/economy.pt", 0.15),
        LeagueMember("rush_exploiter", "policy", "outputs/rl_pvp/checkpoints/rush.pt", 0.15),
    ])

    def sample_opponent(self) -> LeagueMember:
        return random.choices(self.members, weights=[m.weight for m in self.members], k=1)[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-play/league scheduler skeleton.")
    parser.add_argument("--config", type=Path, default=Path("configs/rl_pvp/mappo.yaml"))
    parser.add_argument("--rounds", type=int, default=1)
    args = parser.parse_args()
    league = League()
    for i in range(args.rounds):
        opp = league.sample_opponent()
        print(f"round={i} opponent={opp.name} mode={opp.mode} checkpoint={opp.checkpoint}")
    print("TODO: launch self-play jobs, add historical checkpoints, run held-out evaluation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
