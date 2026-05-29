from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import torch
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, TensorDataset, random_split
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"PyTorch is required for BC training: {exc}")

REPO_ROOT = Path(__file__).resolve().parents[2]
PY_ROOT = REPO_ROOT / "CAPI" / "python"
if str(PY_ROOT) not in sys.path:
    sys.path.insert(0, str(PY_ROOT))


def load_cfg(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except Exception:
        data: Dict[str, Any] = {}
        for raw in text.splitlines():
            if ":" in raw and not raw.startswith(" "):
                k, v = raw.split(":", 1)
                data[k.strip()] = _coerce(v.strip())
        return data


def _coerce(v: str):
    if v.lower() in {"true", "false"}:
        return v.lower() == "true"
    try:
        return int(v)
    except Exception:
        pass
    try:
        return float(v)
    except Exception:
        return v.strip('"\'')


def label_dim(t: torch.Tensor) -> int:
    valid = t[t >= 0]
    return int(valid.max().item() + 1) if valid.numel() else 1


def masked_ce(logits, target, mask=None):
    valid = target >= 0
    if not valid.any():
        return logits.sum() * 0.0
    return F.cross_entropy(logits[valid], target[valid])


def acc_topk(logits, target, k: int) -> float:
    valid = target >= 0
    if not valid.any():
        return 0.0
    kk = min(k, logits.shape[-1])
    pred = logits[valid].topk(kk, dim=-1).indices
    return float((pred == target[valid].unsqueeze(-1)).any(dim=-1).float().mean().item())


def run_epoch(model, loader, optimizer, cfg, device, train: bool) -> Dict[str, float]:
    model.train(train)
    totals = {"loss": 0.0, "n": 0, "top1": 0.0, "top3": 0.0, "valid_action": 0.0, "strategic": 0.0, "role": 0.0}
    weights = cfg.get("loss", {}) or {}
    for batch in loader:
        obs, action, mask, strategic, role, goods, amount = [x.to(device) for x in batch]
        if train:
            optimizer.zero_grad(set_to_none=True)
        out = model(obs, action_mask=mask if cfg.get("use_action_mask_loss", True) else None)
        action_logits = out["action_logits"]
        loss = float(weights.get("action_ce", 1.0)) * F.cross_entropy(action_logits, action)
        loss = loss + float(weights.get("strategic_state_ce", 0.2)) * masked_ce(out["strategic_state_logits"], strategic)
        loss = loss + float(weights.get("role_assignment_ce", 0.2)) * masked_ce(out["role_assignment_logits"], role)
        loss = loss + float(weights.get("goods_type_ce", 0.1)) * masked_ce(out["goods_type_logits"], goods)
        loss = loss + float(weights.get("amount_bucket_ce", 0.1)) * masked_ce(out["amount_bucket_logits"], amount)
        if train:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(cfg.get("grad_clip_norm", 1.0)))
            optimizer.step()
        n = obs.shape[0]
        pred = action_logits.argmax(dim=-1)
        totals["loss"] += float(loss.item()) * n
        totals["top1"] += float((pred == action).float().mean().item()) * n
        totals["top3"] += acc_topk(action_logits, action, 3) * n
        totals["valid_action"] += float(mask.gather(1, pred.view(-1, 1)).float().mean().item()) * n
        totals["strategic"] += acc_topk(out["strategic_state_logits"], strategic, 1) * n
        totals["role"] += acc_topk(out["role_assignment_logits"], role, 1) * n
        totals["n"] += n
    n = max(1, int(totals["n"]))
    return {"loss": totals["loss"] / n, "action_acc_top1": totals["top1"] / n, "action_acc_top3": totals["top3"] / n, "valid_action_rate": totals["valid_action"] / n, "strategic_state_acc": totals["strategic"] / n, "role_assignment_acc": totals["role"] / n}


def main() -> int:
    ap = argparse.ArgumentParser(description="Train THUAI9 Stage4 behavior cloning policy.")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--config", type=Path, default=Path("configs/rl_pvp/bc.yaml"))
    ap.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/checkpoints/bc/latest.pt"))
    args = ap.parse_args()
    data_path = args.data if args.data.is_absolute() else REPO_ROOT / args.data
    cfg_path = args.config if args.config.is_absolute() else REPO_ROOT / args.config
    out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    cfg = load_cfg(cfg_path)
    seed = int(cfg.get("seed", 0)); random.seed(seed); torch.manual_seed(seed)
    device_name = cfg.get("device", "auto")
    device = torch.device("cuda" if device_name == "auto" and torch.cuda.is_available() else ("cpu" if device_name == "auto" else device_name))
    data = torch.load(data_path, map_location="cpu")
    ds = TensorDataset(data["obs"], data["action"], data["action_mask"], data["strategic_state"], data["role_assignment"], data["goods_type"], data["amount_bucket"])
    val_n = max(1, int(len(ds) * float(cfg.get("validation_split", 0.1)))) if len(ds) > 1 else 0
    train_n = len(ds) - val_n
    train_ds, val_ds = random_split(ds, [train_n, val_n], generator=torch.Generator().manual_seed(seed)) if val_n else (ds, ds)
    from PyAPI.rl_agent.models import THUAI9BCPolicy
    from PyAPI.rl_agent.action_space import ACTION_SPACE_VERSION
    model = THUAI9BCPolicy(obs_dim=int(data["obs_dim"]), action_dim=int(data["num_actions"]), hidden_dim=int(cfg.get("hidden_dim", 128)), strategic_dim=label_dim(data["strategic_state"]), role_dim=label_dim(data["role_assignment"]), goods_dim=label_dim(data["goods_type"]), amount_dim=label_dim(data["amount_bucket"])).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg.get("learning_rate", 3e-4)), weight_decay=float(cfg.get("weight_decay", 1e-5)))
    train_loader = DataLoader(train_ds, batch_size=int(cfg.get("batch_size", 512)), shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=int(cfg.get("batch_size", 512)), shuffle=False)
    metrics_dir = REPO_ROOT / "outputs/rl_pvp/train_logs/bc"; metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_dir / "metrics.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    best_path = out.parent / "best.pt"
    best = float("inf"); stale = 0
    epochs = int(cfg.get("epochs", 10))
    patience = int(cfg.get("early_stop_patience", 3))
    for epoch in range(1, epochs + 1):
        train = run_epoch(model, train_loader, opt, cfg, device, True)
        with torch.no_grad():
            val = run_epoch(model, val_loader, opt, cfg, device, False)
        row = {"epoch": epoch, "train_loss": train["loss"], "val_loss": val["loss"], "action_acc_top1": val["action_acc_top1"], "action_acc_top3": val["action_acc_top3"], "valid_action_rate": val["valid_action_rate"], "strategic_state_acc": val["strategic_state_acc"], "role_assignment_acc": val["role_assignment_acc"]}
        with metrics_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        ckpt = {"checkpoint_type": "bc", "model_state_dict": model.state_dict(), "obs_dim": int(data["obs_dim"]), "num_actions": int(data["num_actions"]), "action_dim": int(data["num_actions"]), "hidden_dim": int(cfg.get("hidden_dim", 128)), "obs_schema_version": "stage4_v1", "action_space_version": ACTION_SPACE_VERSION, "label_maps": data.get("label_maps", {}), "config": cfg}
        torch.save(ckpt, out)
        if val["loss"] < best:
            best = val["loss"]; stale = 0; torch.save(ckpt, best_path)
        else:
            stale += 1
        print(json.dumps(row, ensure_ascii=False))
        if stale >= patience:
            break
    print(out)
    print(best_path)
    print(metrics_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
