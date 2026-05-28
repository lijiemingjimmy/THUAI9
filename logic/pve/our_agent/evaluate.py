from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PVE_ROOT = Path(__file__).resolve().parents[1]
if str(PVE_ROOT) not in sys.path:
    sys.path.insert(0, str(PVE_ROOT))

from GameLogic import GameConfig, GameEnvironment
from our_agent.agent import Agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate our THUAI9 PvE agent.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--config", default="hard", choices=["easy", "medium", "hard"])
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 42, 123, 999])
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    cfg_factory = {
        "easy": GameConfig.easy,
        "medium": GameConfig.medium,
        "hard": GameConfig.hard,
    }[args.config]

    per_seed = []
    for seed in args.seeds:
        cfg = cfg_factory()
        cfg.random_map = True
        env = GameEnvironment(cfg=cfg, seed=seed)
        agent = Agent.load(args.model, env)
        scores = []
        rewards = []
        lengths = []

        for ep in range(args.episodes):
            obs, _ = env.reset(seed=seed * 10_000 + ep)
            done = False
            ep_reward = 0.0
            ep_score = 0.0
            ep_len = 0
            while not done:
                action = agent.get_action(obs)
                obs, reward, terminated, truncated, info = env.step(action)
                done = terminated or truncated
                ep_reward += reward
                ep_score = float(info.get("score", ep_score))
                ep_len += 1
            scores.append(ep_score)
            rewards.append(ep_reward)
            lengths.append(ep_len)

        result = {
            "seed": seed,
            "score_mean": float(np.mean(scores)),
            "score_std": float(np.std(scores)),
            "reward_mean": float(np.mean(rewards)),
            "length_mean": float(np.mean(lengths)),
        }
        per_seed.append(result)
        print(
            f"seed={seed} score={result['score_mean']:.2f} "
            f"+/- {result['score_std']:.2f} reward={result['reward_mean']:.3f}"
        )

    overall = {
        "model": args.model,
        "config": args.config,
        "episodes": args.episodes,
        "per_seed": per_seed,
        "score_mean": float(np.mean([r["score_mean"] for r in per_seed])),
        "score_std": float(np.std([r["score_mean"] for r in per_seed])),
    }
    print(json.dumps(overall, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(overall, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
