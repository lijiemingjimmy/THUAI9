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
    invalid_by_action = Counter()
    invalid_by_reason = Counter()
    invalid_by_player = Counter()
    invalid_by_fsm_state = Counter()
    invalid_by_time_bucket = Counter()
    valid_rows: List[Dict[str, Any]] = []
    economy = Counter()
    first_times: Dict[str, list] = defaultdict(list)
    economy_timeline: List[Dict[str, Any]] = []
    last_material_by_team: Dict[tuple[str, int], int] = {}
    strategic_dist = Counter()
    role_dist = Counter()
    role_switch_events = Counter()
    center_metrics = Counter()
    combat_metrics = Counter()
    bc_ready = Counter()
    bc_action_counter = Counter()

    for row in rows:
        if "_parse_error" in row:
            parse_errors += 1
            warnings.append(f"parse error {row['_path']}:{row['_line']}: {row['_parse_error']}")
            continue
        valid_rows.append(row)
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
        strategic_dist[str(row.get("strategic_state") or "none")] += 1
        role_dist[str(row.get("role_assignment") or "none")] += 1
        if row.get("role_switch_reason"):
            role_switch_events[str(row.get("role_switch_reason"))] += 1
        if row.get("center_occupied"):
            center_metrics["center_occupied_rows"] += 1
        if action == "OCCUPY_CENTER" and row.get("action_success"):
            center_metrics["occupy_started"] += 1
        if action in {"ATTACK_NEAREST_ENEMY", "GO_ENEMY", "PRESSURE_ENEMY_FACTORY", "RETREAT"}:
            combat_metrics[action] += 1
        if row.get("obs_vector") is not None:
            bc_ready["num_samples_with_obs"] += 1
        if row.get("macro_action_id") is not None or row.get("raw_action_id") is not None:
            bc_ready["num_samples_with_action"] += 1
        if row.get("action_mask") is not None:
            bc_ready["num_samples_with_mask"] += 1
        mask_for_bc = row.get("action_mask") or []
        action_id_for_bc = row.get("macro_action_id", row.get("raw_action_id"))
        if isinstance(mask_for_bc, list) and action_id_for_bc is not None:
            try:
                aid = int(action_id_for_bc)
                if 0 <= aid < len(mask_for_bc) and bool(mask_for_bc[aid]):
                    bc_ready["num_valid_bc_samples"] += 1
                    bc_action_counter[str(action)] += 1
                else:
                    bc_ready["invalid_label_count"] += 1
            except Exception:
                bc_ready["invalid_label_count"] += 1
        if kind == "team" and len(mask_for_bc) not in {0, 11}:
            bc_ready["mask_mismatch_count"] += 1
        if kind == "character" and len(mask_for_bc) not in {0, 13}:
            bc_ready["mask_mismatch_count"] += 1
        if "IDLE" in action or action == "WAIT_BUSY":
            idle += 1
        ok = bool(row.get("action_success"))
        success += int(ok)
        failure += int(not ok)
        invalid += int(not ok)
        if not ok:
            reason = str(row.get("failure_reason") or row.get("contract_reason") or "unknown")
            fsm_state = str(row.get("fsm_state") or "none")
            invalid_by_action[action] += 1
            invalid_by_reason[reason] += 1
            invalid_by_player[f"g={game}:t={team}:p={player}"] += 1
            invalid_by_fsm_state[fsm_state] += 1
            invalid_by_time_bucket[f"{(tick // 1000) * 1000}-{(tick // 1000 + 1) * 1000}"] += 1
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
        event_time = row.get("game_time") if row.get("game_time") is not None else row.get("timestamp_ms", 0)
        economy_event = str(row.get("economy_event") or "")
        fsm_state = str(row.get("fsm_state") or "")
        if action == "HARVEST" and ok:
            economy["num_harvest_started"] += 1
            first_times["first_harvest_time"].append(event_time)
        if action.startswith("PRODUCE_") or economy_event.startswith("produce"):
            economy["num_produce_requested"] += 1
            first_times["first_produce_time"].append(event_time)
            if ok and economy_event == "produce_succeeded":
                economy["num_produce_succeeded"] += 1
        if action == "LOAD_GOODS" and ok:
            economy["num_load_succeeded"] += 1
            first_times["first_load_time"].append(event_time)
        if action == "SELL_GOODS" and ok:
            economy["num_sell_succeeded"] += 1
            economy["economy_loop_completed_count"] += 1
            first_times["first_sell_time"].append(event_time)
        if fsm_state == "RETURN_FACTORY":
            economy["num_returned_to_factory"] += 1
        if fsm_state == "WAIT_PRODUCTION":
            economy["factory_wait_steps"] += 1
        if fsm_state in {"MOVE_TO_MARKET", "ALIGN_MARKET", "SELL_GOODS"}:
            economy["market_wait_steps"] += 1
        if (row.get("observation_summary") or {}).get("self_state", {}).get("goods_total", 0):
            economy["goods_carried_steps"] += 1
        key_tm = (game, team)
        mat = int(row.get("raw_material") or 0)
        prev_mat = last_material_by_team.get(key_tm)
        if prev_mat is not None and mat > prev_mat:
            economy["num_harvest_completed"] += 1
        last_material_by_team[key_tm] = mat
        economy_timeline.append({
            "game_id": game, "team_id": team, "player_id": player, "game_tick": tick,
            "game_time": row.get("game_time"), "macro_action": action, "success": ok,
            "reason": row.get("failure_reason") or row.get("contract_reason") or "",
            "fsm_state": row.get("fsm_state") or "", "score": row.get("score"),
            "material": row.get("raw_material"), "goods_total": (row.get("observation_summary") or {}).get("self_state", {}).get("goods_total", 0),
        })

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

    economy_summary = dict(economy)
    for key, values in first_times.items():
        clean = [float(v) for v in values if v is not None]
        economy_summary[key] = min(clean) if clean else None
    economy_summary["economy_loop_success_rate"] = (economy_summary.get("num_sell_succeeded", 0) / max(1, economy_summary.get("num_harvest_started", 0)))
    economy_summary["mean_time_to_first_sell"] = mean([float(v) for v in first_times.get("first_sell_time", [])]) if first_times.get("first_sell_time") else None
    economy_summary["goods_carried_time"] = economy_summary.get("goods_carried_steps", 0) * 0.3
    economy_summary["factory_wait_time"] = economy_summary.get("factory_wait_steps", 0) * 0.3
    economy_summary["market_wait_time"] = economy_summary.get("market_wait_steps", 0) * 0.3

    total_bc_actions = sum(bc_action_counter.values())
    bc_entropy = 0.0
    if total_bc_actions:
        for count in bc_action_counter.values():
            p = count / total_bc_actions
            bc_entropy -= p * math.log(max(p, 1e-12))
    bc_dataset_readiness = dict(bc_ready)
    bc_dataset_readiness["action_distribution_entropy"] = bc_entropy
    bc_dataset_readiness["recommended_for_bc"] = bool(bc_ready.get("num_valid_bc_samples", 0) >= 100 and bc_ready.get("mask_mismatch_count", 0) == 0)

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
        "invalid_by_action": dict(invalid_by_action),
        "invalid_by_reason": dict(invalid_by_reason),
        "invalid_by_player": dict(invalid_by_player),
        "invalid_by_fsm_state": dict(invalid_by_fsm_state),
        "invalid_by_game_time_bucket": dict(invalid_by_time_bucket),
        "economy_metrics": economy_summary,
        "economy_timeline": economy_timeline,
        "strategic_state_distribution": dict(strategic_dist),
        "role_assignment_distribution": dict(role_dist),
        "role_switch_events": dict(role_switch_events),
        "center_metrics": dict(center_metrics),
        "combat_metrics": dict(combat_metrics),
        "bc_dataset_readiness": bc_dataset_readiness,
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


def counter_rows(data: Dict[str, int], key_name: str) -> List[Dict[str, Any]]:
    total = sum(int(v) for v in data.values())
    return [{key_name: k, "count": v, "rate": v / total if total else 0.0} for k, v in sorted(data.items(), key=lambda kv: (-kv[1], kv[0]))]


def invalid_examples_markdown(summary: Dict[str, Any], rows: List[Dict[str, Any]], limit: int = 20) -> str:
    rows = [r for r in rows if "_parse_error" not in r]
    rows.sort(key=lambda r: (str(r.get("game_id")), int(r.get("team_id") or 0), int(r.get("player_id") or 0), int(r.get("timestamp_ms") or 0)))
    lines: List[str] = []
    by_key: Dict[tuple[str, int, int], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_key[(str(r.get("game_id")), int(r.get("team_id") or 0), int(r.get("player_id") or 0))].append(r)
    emitted = 0
    for key, seq in by_key.items():
        for idx, r in enumerate(seq):
            if bool(r.get("action_success")):
                continue
            obs = r.get("observation_summary") or {}
            prev = [x.get("macro_action_name") for x in seq[max(0, idx - 3):idx]]
            nxt = [x.get("macro_action_name") for x in seq[idx + 1:idx + 4]]
            lines.append(f"## example {emitted + 1}")
            lines.append(f"- game/team/player: {key[0]} / {key[1]} / {key[2]}")
            lines.append(f"- timestamp_ms: {r.get('timestamp_ms')} tick: {r.get('game_tick')}")
            lines.append(f"- fsm_state: {r.get('fsm_state')}")
            lines.append(f"- action: {r.get('macro_action_name')} target: {r.get('target')}")
            lines.append(f"- precondition/capi: {r.get('contract_reason') or r.get('failure_reason')} / success={r.get('action_success')}")
            lines.append(f"- obs: score={r.get('score')} mat={r.get('raw_material')} hp={r.get('factory_hp')} self={obs.get('self_state', {})}")
            lines.append(f"- prev3: {prev}")
            lines.append(f"- next3: {nxt}\n")
            emitted += 1
            if emitted >= limit:
                return "\n".join(lines)
    return "\n".join(lines) if lines else "no invalid examples\n"


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
    write_csv(args.out / "invalid_by_action.csv", counter_rows(summary.get("invalid_by_action", {}), "macro_action"))
    write_csv(args.out / "invalid_by_reason.csv", counter_rows(summary.get("invalid_by_reason", {}), "reason"))
    write_csv(args.out / "invalid_by_fsm_state.csv", counter_rows(summary.get("invalid_by_fsm_state", {}), "fsm_state"))
    write_csv(args.out / "economy_timeline.csv", summary.get("economy_timeline", []))
    write_csv(args.out / "strategic_state_distribution.csv", counter_rows(summary.get("strategic_state_distribution", {}), "strategic_state"))
    write_csv(args.out / "role_assignment_distribution.csv", counter_rows(summary.get("role_assignment_distribution", {}), "role_assignment"))
    write_csv(args.out / "role_switch_events.csv", counter_rows(summary.get("role_switch_events", {}), "reason"))
    (args.out / "economy_metrics.json").write_text(json.dumps(summary.get("economy_metrics", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "center_metrics.json").write_text(json.dumps(summary.get("center_metrics", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "combat_metrics.json").write_text(json.dumps(summary.get("combat_metrics", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "bc_dataset_readiness.json").write_text(json.dumps(summary.get("bc_dataset_readiness", {}), ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "invalid_examples.md").write_text(invalid_examples_markdown(summary, list(iter_rows(args.log_dir))), encoding="utf-8")
    (args.out / "warnings.txt").write_text("\n".join(warnings) + ("\n" if warnings else ""), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["num_games", "total_steps", "invalid_action_rate", "idle_action_rate", "action_success_rate", "reward_zero_rate", "warnings_count"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
