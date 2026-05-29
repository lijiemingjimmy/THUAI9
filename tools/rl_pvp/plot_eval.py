from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot THUAI9 eval/rollout summaries.")
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data = json.loads(args.summary.read_text(encoding="utf-8"))
    out = args.out_dir or args.summary.with_suffix("")
    out.mkdir(parents=True, exist_ok=True)
    scores = [g.get("scores", {}).get(data.get("candidate_team", "Team 1"), 0) for g in data.get("games", [])]
    plt.figure(); plt.plot(scores, marker="o"); plt.title("candidate score per game"); plt.xlabel("game"); plt.ylabel("score"); plt.tight_layout(); plt.savefig(out / "score_curve.png"); plt.close()
    hist = Counter()
    rewards = defaultdict(float)
    for g in data.get("games", []):
        for a in g.get("action_hist", []):
            hist[a.get("macro_action")] += int(a.get("count", 0))
    if hist:
        labels, vals = zip(*hist.most_common(20)); plt.figure(figsize=(10,4)); plt.bar(labels, vals); plt.xticks(rotation=60, ha="right"); plt.tight_layout(); plt.savefig(out / "action_hist.png"); plt.close()
    plt.figure(); plt.text(0.5, 0.5, "reward components: use analyze_rollouts reward_components.csv", ha="center"); plt.axis("off"); plt.tight_layout(); plt.savefig(out / "reward_components.png"); plt.close()
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
