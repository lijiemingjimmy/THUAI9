from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "CAPI" / "python"))
sys.path.insert(0, str(REPO_ROOT / "CAPI" / "python" / "proto"))

from PyAPI.rl_agent.models import THUAI9MAPPO
from PyAPI.rl_agent.observation import OBS_VECTOR_DIM, observation_to_vector, privileged_state_to_vector


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def iter_rows(root: Path):
    for path in sorted(root.rglob("*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    row.setdefault("game_id", path.parent.parent.name if path.parent.name == "agent_jsonl" else path.parent.name)
                    yield row


def build_samples(rows, obs_dim, state_dim, action_dim):
    latest_team_state: Dict[tuple, Dict[str, Any]] = {}
    ordered = []
    for r in rows:
        obs = r.get("observation_summary") or {}
        key = (r.get("game_id"), r.get("team_id"))
        latest_team_state[key] = obs
        ordered.append(r)
    samples = []
    for r in ordered:
        obs = r.get("observation_summary") or {}
        mask = list(r.get("action_mask") or [])[:action_dim]
        if not mask or not any(mask):
            continue
        if len(mask) < action_dim:
            mask += [0] * (action_dim - len(mask))
        action = int(r.get("raw_action_id", 0))
        if action >= action_dim or action < 0 or not mask[action]:
            legal = [i for i, ok in enumerate(mask) if ok]
            if not legal:
                continue
            action = legal[0]
        state_src = latest_team_state.get((r.get("game_id"), r.get("team_id")), obs)
        samples.append({
            "obs": observation_to_vector(obs, obs_dim),
            "state": privileged_state_to_vector(state_src, state_dim),
            "mask": mask,
            "action": action,
            "reward": float(r.get("reward") or 0.0),
            "old_log_prob": r.get("log_prob"),
            "old_value": r.get("value"),
            "group": (str(r.get("game_id")), int(r.get("team_id") or 0), int(r.get("player_id") or 0)),
            "tick": int(r.get("game_tick") or 0),
        })
    samples.sort(key=lambda x: (x["group"], x["tick"]))
    return samples


def returns_adv(samples, gamma, lam):
    groups: Dict[tuple, List[int]] = {}
    for i, s in enumerate(samples):
        groups.setdefault(s["group"], []).append(i)
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
    parser = argparse.ArgumentParser(description="Minimal MAPPO: shared actor + centralized critic approximation.")
    parser.add_argument("--config", type=Path, default=Path("configs/rl_pvp/mappo.yaml"))
    parser.add_argument("--data", type=Path, default=Path("outputs/rl_pvp/logs"))
    parser.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/checkpoints/mappo/latest.pt"))
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    import torch
    import torch.nn.functional as F
    obs_dim = int(cfg.get("obs_dim", OBS_VECTOR_DIM)); state_dim = int(cfg.get("state_dim", OBS_VECTOR_DIM)); action_dim = int(cfg.get("action_dim", 16)); hidden_dim = int(cfg.get("hidden_dim", 128))
    gamma = float(cfg.get("gamma", 0.995)); lam = float(cfg.get("gae_lambda", 0.95)); clip = float(cfg.get("clip_range", 0.2)); lr = float(cfg.get("learning_rate", 3e-4)); epochs = int(cfg.get("epochs", 3)); mb = int(cfg.get("minibatch_size", 256)); batch_size = int(cfg.get("batch_size", 4096))
    samples = build_samples(list(iter_rows(args.data)), obs_dim, state_dim, action_dim)
    if not samples:
        raise SystemExit(f"no usable rollout samples under {args.data}")
    if len(samples) > batch_size:
        samples = samples[-batch_size:]
    rets, adv = returns_adv(samples, gamma, lam)
    obs = torch.tensor([s["obs"] for s in samples], dtype=torch.float32, device=args.device)
    states = torch.tensor([s["state"] for s in samples], dtype=torch.float32, device=args.device)
    masks = torch.tensor([s["mask"] for s in samples], dtype=torch.bool, device=args.device)
    actions = torch.tensor([s["action"] for s in samples], dtype=torch.long, device=args.device)
    returns_t = torch.tensor(rets, dtype=torch.float32, device=args.device)
    adv_t = torch.tensor(adv, dtype=torch.float32, device=args.device)
    if len(adv_t) > 1:
        adv_t = (adv_t - adv_t.mean()) / (adv_t.std(unbiased=False) + 1e-8)
    old_logp = torch.tensor([float(s["old_log_prob"] or 0.0) for s in samples], dtype=torch.float32, device=args.device)
    has_old = torch.tensor([s["old_log_prob"] is not None for s in samples], dtype=torch.bool, device=args.device)
    model = THUAI9MAPPO(obs_dim=obs_dim, state_dim=state_dim, action_dim=action_dim, hidden_dim=hidden_dim).to(args.device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    metrics_dir = REPO_ROOT / "outputs" / "rl_pvp" / "train_logs" / "mappo"; metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_dir / "metrics.jsonl"
    last = {}
    n = len(samples)
    for ep in range(epochs):
        order = list(range(n)); random.shuffle(order)
        for st in range(0, n, mb):
            idx = torch.tensor(order[st:st+mb], dtype=torch.long, device=args.device)
            logits, values, _ = model(obs[idx], states[idx], masks[idx])
            dist = torch.distributions.Categorical(logits=logits)
            lp = dist.log_prob(actions[idx]); ent = dist.entropy().mean()
            if has_old[idx].any():
                ratio = torch.exp(lp - old_logp[idx])
                pol = -torch.min(ratio * adv_t[idx], torch.clamp(ratio, 1-clip, 1+clip) * adv_t[idx]).mean()
            else:
                pol = F.cross_entropy(logits, actions[idx])
            vloss = F.mse_loss(values, returns_t[idx])
            loss = pol + float(cfg.get("value_coef", 0.5)) * vloss - float(cfg.get("entropy_coef", 0.01)) * ent
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), float(cfg.get("max_grad_norm", 0.5))); opt.step()
            last = {"epoch": ep, "samples": n, "loss": float(loss.item()), "policy_loss": float(pol.item()), "value_loss": float(vloss.item()), "entropy": float(ent.item()), "ppo_fraction": float(has_old.float().mean().item()), "critic": "latest-team-state approximation"}
            metrics_path.open("a", encoding="utf-8").write(json.dumps(last, ensure_ascii=False)+"\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"model": model.state_dict(), "obs_dim": obs_dim, "state_dim": state_dim, "action_dim": action_dim, "hidden_dim": hidden_dim, "metrics": last, "mappo_approximation": "critic uses latest team/global observation per team when exact timestamp alignment is unavailable"}
    torch.save(payload, args.out); torch.save(payload, args.out.parent / f"step_{len(list(args.out.parent.glob('step_*.pt'))):06d}.pt")
    print(json.dumps({"checkpoint": str(args.out), **last}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
