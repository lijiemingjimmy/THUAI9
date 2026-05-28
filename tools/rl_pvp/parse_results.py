from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List


def parse_result_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "crashed": True, "scores": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"path": str(path), "crashed": True, "error": str(exc), "scores": {}}
    scores: Dict[str, int] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, (int, float)):
                scores[str(key)] = int(value)
            elif isinstance(value, dict) and "score" in value:
                scores[str(key)] = int(value.get("score", 0))
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return {"path": str(path), "crashed": False, "scores": scores, "winner": ranked[0][0] if ranked else None, "ranked": ranked}


def summarize_games(games: Iterable[Dict[str, Any]], candidate_team: str = "Team 1") -> Dict[str, Any]:
    rows = list(games)
    scores = [int(g.get("scores", {}).get(candidate_team, 0)) for g in rows]
    wins = [1 for g in rows if g.get("winner") == candidate_team]
    crashes = [1 for g in rows if g.get("crashed")]
    return {
        "num_games": len(rows),
        "candidate_team": candidate_team,
        "mean_score": mean(scores) if scores else 0.0,
        "score_std": pstdev(scores) if len(scores) > 1 else 0.0,
        "win_rate": len(wins) / len(rows) if rows else 0.0,
        "crash_rate": len(crashes) / len(rows) if rows else 0.0,
        "games": rows,
    }


def write_summary(summary: Dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = out.with_suffix(".csv")
    games = summary.get("games", [])
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "crashed", "winner", "candidate_score"])
        writer.writeheader()
        for g in games:
            writer.writerow({
                "path": g.get("path"),
                "crashed": g.get("crashed"),
                "winner": g.get("winner"),
                "candidate_score": g.get("scores", {}).get(summary.get("candidate_team", "Team 1"), 0),
            })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/eval/summary.json"))
    parser.add_argument("--candidate-team", default="Team 1")
    args = parser.parse_args()
    summary = summarize_games([parse_result_file(p) for p in args.results], args.candidate_team)
    write_summary(summary, args.out)
    print(json.dumps({k: v for k, v in summary.items() if k != "games"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
