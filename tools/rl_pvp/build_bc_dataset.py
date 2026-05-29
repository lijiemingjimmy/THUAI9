from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    import torch
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"PyTorch is required to build BC dataset: {exc}")

REPO_ROOT = Path(__file__).resolve().parents[2]


def iter_rows(log_dirs: Iterable[Path]):
    for root in log_dirs:
        root = root if root.is_absolute() else REPO_ROOT / root
        for path in sorted(root.rglob("*.jsonl")):
            with path.open(encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                        row["_path"] = str(path)
                        row["_line"] = line_no
                        yield row
                    except Exception:
                        continue


def label_id(value: Any, mapping: Dict[str, int]) -> int:
    if value is None or value == "":
        return -1
    key = str(value)
    if key not in mapping:
        mapping[key] = len(mapping)
    return mapping[key]


def entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return -sum((v / total) * math.log(max(v / total, 1e-12)) for v in counter.values())


def main() -> int:
    ap = argparse.ArgumentParser(description="Build THUAI9 Stage4 behavior cloning dataset from rollout JSONL logs.")
    ap.add_argument("--log-dirs", nargs="+", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/bc_data/stage4_bc_dataset.pt"))
    ap.add_argument("--keep-failures", action="store_true")
    args = ap.parse_args()
    out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    label_maps = {"strategic_state": {}, "role_assignment": {}, "target_type": {}, "goods_type": {}, "amount_bucket": {}}
    samples: List[Dict[str, Any]] = []
    drops = Counter()
    actions = Counter()
    roles = Counter()
    states = Counter()
    games = set()
    max_mask = 0
    for row in iter_rows(args.log_dirs):
        games.add(str(row.get("game_id", "unknown")))
        obs = row.get("obs_vector")
        action = row.get("macro_action_id", row.get("raw_action_id"))
        mask = row.get("action_mask")
        if not isinstance(obs, list) or not obs:
            drops["missing_obs_vector"] += 1; continue
        if action is None:
            drops["missing_action"] += 1; continue
        if not isinstance(mask, list) or not mask:
            drops["missing_action_mask"] += 1; continue
        try:
            action_i = int(action)
        except Exception:
            drops["bad_action_id"] += 1; continue
        if action_i < 0 or action_i >= len(mask):
            drops["action_out_of_mask"] += 1; continue
        if not bool(mask[action_i]):
            drops["action_mask_illegal"] += 1; continue
        if not args.keep_failures and (row.get("api_success") is False and row.get("contract_valid") is False):
            drops["bad_failure_sample"] += 1; continue
        max_mask = max(max_mask, len(mask))
        samples.append({
            "obs": [float(x) for x in obs],
            "action": action_i,
            "mask": [bool(x) for x in mask],
            "strategic_state": label_id(row.get("strategic_state"), label_maps["strategic_state"]),
            "role_assignment": label_id(row.get("role_assignment"), label_maps["role_assignment"]),
            "target_type": label_id(row.get("target_type"), label_maps["target_type"]),
            "goods_type": label_id(row.get("goods_type"), label_maps["goods_type"]),
            "amount_bucket": label_id(row.get("amount_bucket"), label_maps["amount_bucket"]),
        })
        actions[str(row.get("macro_action", row.get("macro_action_name", action_i)))] += 1
        roles[str(row.get("role_assignment"))] += 1
        states[str(row.get("strategic_state"))] += 1
    if not samples:
        raise SystemExit(f"no valid BC samples; dropped={dict(drops)}")
    obs_dim = len(samples[0]["obs"])
    max_mask = max(max_mask, max(s["action"] for s in samples) + 1)
    def pad_mask(m):
        return m + [False] * (max_mask - len(m))
    data = {
        "obs": torch.tensor([s["obs"] for s in samples], dtype=torch.float32),
        "action": torch.tensor([s["action"] for s in samples], dtype=torch.long),
        "action_mask": torch.tensor([pad_mask(s["mask"]) for s in samples], dtype=torch.bool),
        "strategic_state": torch.tensor([s["strategic_state"] for s in samples], dtype=torch.long),
        "role_assignment": torch.tensor([s["role_assignment"] for s in samples], dtype=torch.long),
        "target_type": torch.tensor([s["target_type"] for s in samples], dtype=torch.long),
        "goods_type": torch.tensor([s["goods_type"] for s in samples], dtype=torch.long),
        "amount_bucket": torch.tensor([s["amount_bucket"] for s in samples], dtype=torch.long),
        "label_maps": label_maps,
        "obs_dim": obs_dim,
        "num_actions": max_mask,
        "obs_schema_version": "stage4_v1",
    }
    torch.save(data, out)
    summary = {
        "num_samples": len(samples),
        "num_games": len(games),
        "obs_dim": obs_dim,
        "num_actions": max_mask,
        "action_distribution": dict(actions),
        "role_distribution": dict(roles),
        "strategic_state_distribution": dict(states),
        "valid_action_rate": 1.0,
        "dropped_samples_by_reason": dict(drops),
        "action_distribution_entropy": entropy(actions),
    }
    summary_path = out.with_name(out.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(out)
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
