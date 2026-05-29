from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "CAPI" / "python"))
sys.path.insert(0, str(REPO_ROOT / "CAPI" / "python" / "proto"))

from PyAPI.rl_agent.observation import OBS_VECTOR_DIM, observation_to_vector
from PyAPI.rl_agent.models import THUAI9ActorCritic


def load_simple_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        data: Dict[str, Any] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            v = v.strip().strip('"').strip("'")
            try:
                data[k.strip()] = int(v)
            except ValueError:
                try:
                    data[k.strip()] = float(v)
                except ValueError:
                    data[k.strip()] = v
        return data


def iter_jsonl(root: Path):
    for path in sorted(root.rglob("*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    row.setdefault("game_id", path.parent.parent.name if path.parent.name == "agent_jsonl" else path.parent.name)
                    yield row


def build_dataset(rows: List[Dict[str, Any]], obs_dim: int, action_dim: int):
    samples = []
    for row in rows:
        obs = row.get("observation_summary") or {}
        mask = list(row.get("action_mask") or [])[:action_dim]
        if not mask or not any(mask):
            continue
        if len(mask) < action_dim:
            mask += [0] * (action_dim - len(mask))
        action = int(row.get("raw_action_id", 0))
        if action < 0 or action >= action_dim or not mask[action]:
            legal = [i for i, ok in enumerate(mask) if ok]
            if not legal:
                continue
            action = legal[0]
        reward = float(row.get("reward") or 0.0)
        samples.append({
            "obs": observation_to_vector(obs, obs_dim),
            "mask": mask,
            "action": action,
            "reward": reward,
            "old_log_prob": row.get("log_prob"),
            "old_value": row.get("value"),
            "game_id": str(row.get("game_id", "unknown")),
            "player_id": int(row.get("player_id") or 0),
            "team_id": int(row.get("team_id") or 0),
            "tick": int(row.get("game_tick") or 0),
        })
    samples.sort(key=lambda x: (x["game_id"], x["team_id"], x["player_id"], x["tick"]))
    return samples


def compute_returns_adv(samples, gamma: float, lam: float):
    groups: Dict[tuple, List[int]] = {}
    for i, s in enumerate(samples):
        groups.setdefault((s["game_id"], s["team_id"], s["player_id"]), []).append(i)
    returns = [0.0] * len(samples)
    adv = [0.0] * len(samples)
    for idxs in groups.values():
        gae = 0.0
        next_value = 0.0
        for i in reversed(idxs):
            value = float(samples[i]["old_value"] or 0.0)
            delta = samples[i]["reward"] + gamma * next_value - value
            gae = delta + gamma * lam * gae
            adv[i] = gae
            returns[i] = gae + value
            next_value = value
    return returns, adv


def main() -> int:
    parser = argparse.ArgumentParser(description="Train THUAI9 PPO/BC from rollout JSONL.")
    parser.add_argument("--config", type=Path, default=Path("configs/rl_pvp/ppo.yaml"))
    parser.add_argument("--data", type=Path, default=Path("outputs/rl_pvp/logs"))
    parser.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/checkpoints/ppo/latest.pt"))
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    cfg = load_simple_yaml(args.config)
    gamma = float(cfg.get("gamma", 0.995))
    gae_lambda = float(cfg.get("gae_lambda", 0.95))
    clip_range = float(cfg.get("clip_range", 0.2))
    value_coef = float(cfg.get("value_coef", 0.5))
    entropy_coef = float(cfg.get("entropy_coef", 0.01))
    lr = float(cfg.get("learning_rate", 3e-4))
    batch_size = int(cfg.get("batch_size", 4096))
    minibatch_size = int(cfg.get("minibatch_size", 256))
    epochs = int(cfg.get("epochs", 3))
    max_grad_norm = float(cfg.get("max_grad_norm", 0.5))
    obs_dim = int(cfg.get("obs_dim", OBS_VECTOR_DIM))
    action_dim = int(cfg.get("action_dim", 16))
    hidden_dim = int(cfg.get("hidden_dim", 128))

    import torch
    import torch.nn.functional as F

    rows = list(iter_jsonl(args.data))
    samples = build_dataset(rows, obs_dim, action_dim)
    if not samples:
        raise SystemExit(f"no usable rollout samples under {args.data}")
    if len(samples) > batch_size:
        samples = samples[-batch_size:]
    returns, adv = compute_returns_adv(samples, gamma, gae_lambda)
    adv_t = torch.tensor(adv, dtype=torch.float32)
    if bool(cfg.get("normalize_advantage", True)) and len(adv_t) > 1:
        adv_t = (adv_t - adv_t.mean()) / (adv_t.std(unbiased=False) + 1e-8)
    obs = torch.tensor([s["obs"] for s in samples], dtype=torch.float32, device=args.device)
    masks = torch.tensor([s["mask"] for s in samples], dtype=torch.bool, device=args.device)
    actions = torch.tensor([s["action"] for s in samples], dtype=torch.long, device=args.device)
    returns_t = torch.tensor(returns, dtype=torch.float32, device=args.device)
    adv_t = adv_t.to(args.device)
    has_old = [s["old_log_prob"] is not None for s in samples]
    old_log_probs = torch.tensor([float(s["old_log_prob"] or 0.0) for s in samples], dtype=torch.float32, device=args.device)
    ppo_mask = torch.tensor(has_old, dtype=torch.bool, device=args.device)

    model = THUAI9ActorCritic(obs_dim=obs_dim, action_dim=action_dim, hidden_dim=hidden_dim).to(args.device)
    if args.out.exists():
        try:
            ckpt = torch.load(args.out, map_location=args.device)
            model.load_state_dict(ckpt.get("model", ckpt), strict=False)
        except Exception:
            pass
    optim = torch.optim.Adam(model.parameters(), lr=lr)
    metrics_dir = REPO_ROOT / "outputs" / "rl_pvp" / "train_logs" / "ppo"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_dir / "metrics.jsonl"
    n = len(samples)
    last_metrics = {}
    for epoch in range(epochs):
        order = list(range(n))
        random.shuffle(order)
        for start in range(0, n, minibatch_size):
            idx = torch.tensor(order[start:start+minibatch_size], dtype=torch.long, device=args.device)
            logits, values, _ = model(obs[idx], action_mask=masks[idx])
            dist = torch.distributions.Categorical(logits=logits)
            log_probs = dist.log_prob(actions[idx])
            entropy = dist.entropy().mean()
            if ppo_mask[idx].any():
                ratio = torch.exp(log_probs - old_log_probs[idx])
                unclipped = ratio * adv_t[idx]
                clipped = torch.clamp(ratio, 1.0 - clip_range, 1.0 + clip_range) * adv_t[idx]
                policy_loss = -torch.min(unclipped, clipped).mean()
            else:
                policy_loss = F.cross_entropy(logits, actions[idx])
            value_loss = F.mse_loss(values, returns_t[idx])
            loss = policy_loss + value_coef * value_loss - entropy_coef * entropy
            optim.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
            optim.step()
            last_metrics = {
                "epoch": epoch,
                "samples": n,
                "loss": float(loss.item()),
                "policy_loss": float(policy_loss.item()),
                "value_loss": float(value_loss.item()),
                "entropy": float(entropy.item()),
                "ppo_fraction": float(ppo_mask.float().mean().item()),
            }
            with metrics_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(last_metrics, ensure_ascii=False) + "\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    step_path = args.out.parent / f"step_{len(list(args.out.parent.glob('step_*.pt'))):06d}.pt"
    payload = {"model": model.state_dict(), "obs_dim": obs_dim, "action_dim": action_dim, "hidden_dim": hidden_dim, "metrics": last_metrics}
    torch.save(payload, args.out)
    torch.save(payload, step_path)
    print(json.dumps({"checkpoint": str(args.out), "step_checkpoint": str(step_path), **last_metrics}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
