from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple

REQUIRED = {"timestamp_ms", "game_tick", "team_id", "player_id", "kind", "observation_summary", "raw_action_id", "macro_action_name", "action_mask", "action_success", "reward"}


def iter_rows(log_dir: Path):
    for path in sorted(log_dir.rglob("*.jsonl")):
        run = _run_name(path, log_dir)
        with path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    row["_path"] = str(path)
                    row["_line"] = line_no
                    row["game_id"] = row.get("game_id") or run
                    yield row
                except Exception as exc:
                    yield {"_path": str(path), "_line": line_no, "_parse_error": str(exc), "game_id": run}


def _run_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    parts = rel.parts
    if "agent_jsonl" in parts:
        return "/".join(parts[:parts.index("agent_jsonl")]) or root.name
    return parts[0] if len(parts) > 1 else root.name


def analyze(log_dir: Path) -> tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    rows = list(iter_rows(log_dir))
    warnings: List[str] = []
    action_hist = Counter()
    reward_components: Dict[str, float] = defaultdict(float)
    reward_component_counts = Counter()
    by_player = Counter()
    by_team = Counter()
    invalid = 0
    idle = 0
    success = 0
    failure = 0
    missing_fields = Counter()
    mask_bad = 0
    mask_all_false = 0
    nan_rewards = 0
    zero_rewards = 0
    score_curve: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    compute_curve: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    material_curve: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    hp_curve: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    players_by_game: Dict[str, set[tuple[int, int]]] = defaultdict(set)
    last_tick_by_game = defaultdict(int)
    kinds = Counter()
    parse_errors = 0

    for row in rows:
        if "_parse_error" in row:
            parse_errors += 1
            warnings.append(f"parse error {row['_path']}:{row['_line']}: {row['_parse_error']}")
            continue
        missing = REQUIRED - row.keys()
        for m in missing:
            missing_fields[m] += 1
        game = str(row.get("game_id", "unknown"))
        team = int(row.get("team_id") or 0)
        player = int(row.get("player_id") or 0)
        kind = str(row.get("kind", ""))
        kinds[kind] += 1
        by_player[f"g={game}:t={team}:p={player}"] += 1
        by_team[f"g={game}:t={team}"] += 1
        players_by_game[game].add((team, player))
        tick = int(row.get("game_tick") or 0)
        last_tick_by_game[game] = max(last_tick_by_game[game], tick)
        action = str(row.get("macro_action_name", "UNKNOWN"))
        action_hist[action] += 1
        if "IDLE" in action or action == "WAIT_BUSY":
            idle += 1
        ok = bool(row.get("action_success"))
        success += int(ok)
        failure += int(not ok)
        invalid += int(not ok)
        reward = row.get("reward", 0.0)
        try:
            reward_f = float(reward)
            if math.isnan(reward_f) or math.isinf(reward_f):
                nan_rewards += 1
            if reward_f == 0.0:
                zero_rewards += 1
        except Exception:
            nan_rewards += 1
        for k, v in (row.get("reward_components") or {}).items():
            try:
                reward_components[k] += float(v)
                reward_component_counts[k] += 1
            except Exception:
                pass
        mask = row.get("action_mask") or []
        expected = 11 if kind == "team" else 13 if kind == "character" else len(mask)
        if len(mask) != expected:
            mask_bad += 1
        if mask and not any(bool(x) for x in mask):
            mask_all_false += 1
        elif not mask:
            mask_all_false += 1
        team_key = str(team)
        point = [tick, row.get("score", 0)]
        score_curve[game][team_key].append(point)
        compute_curve[game][team_key].append([tick, row.get("computing_power", 0)])
        material_curve[game][team_key].append([tick, row.get("raw_material", 0)])
        hp_curve[game][team_key].append([tick, row.get("factory_hp", 0)])

    total = len([r for r in rows if "_parse_error" not in r])
    games = sorted(set(last_tick_by_game))
    for game in games:
        players = players_by_game[game]
        teams = sorted({t for t, _ in players})
        for t in teams:
            if (t, 0) not in players:
                warnings.append(f"{game}: team {t} missing player0 team log")
            char_ids = sorted(p for tt, p in players if tt == t and p > 0)
            if not char_ids:
                warnings.append(f"{game}: team {t} has no character logs, BuildCharacter may have failed")
    if missing_fields:
        warnings.append("missing fields: " + json.dumps(dict(missing_fields), ensure_ascii=False))
    if mask_bad:
        warnings.append(f"mask dimension mismatch rows={mask_bad}")
    if mask_all_false:
        warnings.append(f"empty/all-false mask rows={mask_all_false}")
    if nan_rewards:
        warnings.append(f"NaN/invalid reward rows={nan_rewards}")
    if total and zero_rewards / total > 0.9:
        warnings.append(f"reward mostly zero: {zero_rewards}/{total}")

    summary = {
        "log_dir": str(log_dir),
        "num_games": len(games),
        "games": games,
        "total_steps": total,
        "parse_errors": parse_errors,
        "steps_by_player": dict(by_player),
        "steps_by_team": dict(by_team),
        "kind_counts": dict(kinds),
        "invalid_action_rate": invalid / total if total else 0.0,
        "idle_action_rate": idle / total if total else 0.0,
        "action_success_rate": success / total if total else 0.0,
        "action_failure_rate": failure / total if total else 0.0,
        "reward_zero_rate": zero_rewards / total if total else 0.0,
        "mask_bad_rows": mask_bad,
        "mask_all_false_rows": mask_all_false,
        "last_tick_by_game": dict(last_tick_by_game),
        "score_curve": score_curve,
        "computing_power_curve": compute_curve,
        "raw_material_curve": material_curve,
        "factory_hp_curve": hp_curve,
        "warnings_count": len(warnings),
    }
    action_rows = [{"macro_action": k, "count": v, "rate": v / total if total else 0.0} for k, v in action_hist.most_common()]
    comp_rows = [{"component": k, "sum": v, "mean": v / max(1, reward_component_counts[k]), "count": reward_component_counts[k]} for k, v in sorted(reward_components.items())]
    return summary, action_rows, comp_rows, warnings


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze THUAI9 rollout JSONL logs.")
    parser.add_argument("--log-dir", type=Path, default=Path("outputs/rl_pvp/logs"))
    parser.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/analysis/latest"))
    args = parser.parse_args()
    summary, action_rows, comp_rows, warnings = analyze(args.log_dir)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(args.out / "action_hist.csv", action_rows)
    write_csv(args.out / "reward_components.csv", comp_rows)
    (args.out / "warnings.txt").write_text("\n".join(warnings) + ("\n" if warnings else ""), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["num_games", "total_steps", "invalid_action_rate", "idle_action_rate", "action_success_rate", "reward_zero_rate", "warnings_count"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
