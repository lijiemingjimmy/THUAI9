from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

PVE_ROOT = Path(__file__).resolve().parents[1]
if str(PVE_ROOT) not in sys.path:
    sys.path.insert(0, str(PVE_ROOT))

from GameLogic import GameConfig, GameEnvironment
from our_agent.agent import Agent, AgentConfig


def load_config(name_or_path: str) -> GameConfig:
    presets = {
        "easy": GameConfig.easy,
        "medium": GameConfig.medium,
        "hard": GameConfig.hard,
    }
    if name_or_path in presets:
        return presets[name_or_path]()
    with open(name_or_path, "r", encoding="utf-8") as f:
        return GameConfig.from_dict(yaml.safe_load(f))


def main() -> None:
    parser = argparse.ArgumentParser(description="Train our THUAI9 PvE masked Double-DQN agent.")
    parser.add_argument("--config", default="hard", help="easy/medium/hard or YAML path")
    parser.add_argument("--timesteps", type=int, default=2_000_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default=None, help="cpu, cuda, cuda:0, ...")
    parser.add_argument("--save-dir", default="models/our_agent")
    parser.add_argument("--resume", default=None, help="Optional model.pt to resume from")
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--buffer-capacity", type=int, default=500_000)
    parser.add_argument("--learning-starts", type=int, default=10_000)
    parser.add_argument("--epsilon-start", type=float, default=1.0)
    parser.add_argument("--epsilon-end", type=float, default=0.05)
    parser.add_argument("--epsilon-decay", type=int, default=500_000)
    parser.add_argument("--heuristic-start", type=float, default=0.80)
    parser.add_argument("--heuristic-end", type=float, default=0.05)
    parser.add_argument("--heuristic-decay", type=int, default=800_000)
    parser.add_argument("--heuristic-q-bonus", type=float, default=2.0)
    parser.add_argument("--log-every", type=int, default=10_000)
    parser.add_argument("--save-every", type=int, default=100_000)
    parser.add_argument("--random-map", action="store_true", default=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    cfg.random_map = args.random_map
    env = GameEnvironment(cfg=cfg, seed=args.seed)
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    model_path = save_dir / "model.pt"

    agent_config = AgentConfig(
        hidden_dim=args.hidden_dim,
        lr=args.lr,
        gamma=args.gamma,
        batch_size=args.batch_size,
        buffer_capacity=args.buffer_capacity,
        learning_starts=args.learning_starts,
        epsilon_start=args.epsilon_start,
        epsilon_end=args.epsilon_end,
        epsilon_decay=args.epsilon_decay,
        heuristic_start=args.heuristic_start,
        heuristic_end=args.heuristic_end,
        heuristic_decay=args.heuristic_decay,
        heuristic_q_bonus=args.heuristic_q_bonus,
    )

    if args.resume:
        agent = Agent.load(args.resume, env)
        if args.device:
            agent.move_to_device(args.device)
    else:
        agent = Agent(env, config=agent_config, device=args.device, seed=args.seed)

    print(f"[train] config={args.config} random_map={cfg.random_map} seed={args.seed}")
    print(f"[train] device={agent.device} save={model_path}")
    if str(agent.device).startswith("cuda"):
        import torch

        print(
            f"[train] torch_cuda_available={torch.cuda.is_available()} "
            f"device_count={torch.cuda.device_count()}"
        )

    metrics = agent.train(
        args.timesteps,
        log_every=args.log_every,
        save_every=args.save_every,
        save_path=str(model_path),
    )
    agent.save(str(model_path))

    metrics_path = save_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"[train] saved model to {model_path}")
    print(f"[train] saved metrics to {metrics_path}")


if __name__ == "__main__":
    main()
