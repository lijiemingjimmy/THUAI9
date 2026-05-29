from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]

SEMANTICS = {
    "Harvest": {"range": "resource nine-grid by cell", "kind": "continuous; state HARVESTING; repeated calls while busy fail", "output": "team factory source/team.material, not character goodsLoad/currentLoad", "completion": "resource depleted, interrupted, leaves range, or thread ends"},
    "ProduceGoods": {"range": "team process only; no character near factory", "precondition": "factory exists, canProduce, enough material/source, storage room, amount>0", "queue": "no queue; one production at a time", "output": "factory.productInventory", "amount": "requested item count; can stop early"},
    "Load": {"range": "own factory nine-grid", "precondition": "idle, amount>0, inventory enough, capacity room", "output": "character.goodsLoad/currentLoad"},
    "Sell": {"range": "market nine-grid", "precondition": "idle, amount>0, carried goods enough", "output": "score immediately increases; goodsLoad/currentLoad decrease"},
    "Occupy": {"range": "compute center nine-grid", "precondition": "Drone/Robot, idle, center nearby", "kind": "continuous; state OCUPPYING; progress while in range"},
    "BuildCharacter": {"precondition": "team process, canRecruit, enough compute, unused player id, under limit"},
    "UplevelTech": {"precondition": "team process, enough compute"},
    "Move": {"input": "angle in world coordinates; target cell uses center world position"},
    "EndAllAction": {"effect": "interrupts current character action when accepted"},
}


def iter_jsonl(log_dir: Path) -> Iterable[Dict[str, Any]]:
    for path in log_dir.rglob("*.jsonl"):
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    row["_path"] = str(path)
                    yield row


def write_probe_files(log_dir: Path, out: Path) -> None:
    groups = {
        "harvest_probe.jsonl": lambda a: a in {"HARVEST", "WAIT_BUSY"},
        "produce_probe.jsonl": lambda a: a.startswith("PRODUCE_"),
        "load_probe.jsonl": lambda a: a == "LOAD_GOODS",
        "sell_probe.jsonl": lambda a: a == "SELL_GOODS",
        "occupy_probe.jsonl": lambda a: a == "OCCUPY_CENTER",
    }
    rows = list(iter_jsonl(log_dir)) if log_dir.exists() else []
    for name, pred in groups.items():
        with (out / name).open("w", encoding="utf-8") as f:
            for row in rows:
                if pred(str(row.get("macro_action_name", ""))):
                    f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_summary(out: Path, ran: bool, log_dir: Path) -> None:
    lines = ["# THUAI9 PvP CAPI Action Semantics", "", f"probe_match_ran: {ran}", f"source_log_dir: {log_dir}", ""]
    for action, items in SEMANTICS.items():
        lines.append(f"## {action}")
        for key, value in items.items():
            lines.append(f"- {key}: {value}")
        lines.append("")
    lines.extend([
        "## Coordinate Contract",
        "- Character x/y are world coordinates; cell = x//1000, y//1000.",
        "- GetResourceState/GetMarketState/GetFactoryState/GetComputeCenterState use cell coordinates.",
        "- Interaction range is nine-grid in cell space.",
    ])
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe THUAI9 PvP CAPI action semantics with real Server logs.")
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--out", type=Path, default=Path("outputs/rl_pvp/probes/action_semantics"))
    parser.add_argument("--skip-run", action="store_true")
    args = parser.parse_args()
    out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    log_dir = REPO_ROOT / "outputs/rl_pvp/logs/action_semantics_probe"
    result = REPO_ROOT / "outputs/rl_pvp/results/action_semantics_probe.json"
    ran = False
    if not args.skip_run:
        env = os.environ.copy()
        env["THUAI9_RULE_PROFILE"] = "economy_only"
        cmd = [sys.executable, "tools/rl_pvp/launch_match.py", "--team-count", "2", "--duration", str(args.duration), "--team0-mode", "rule", "--team1-mode", "random", "--result", str(result), "--log-dir", str(log_dir), "--skip-build", "--skip-proto"]
        proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, timeout=args.duration + 150)
        ran = proc.returncode == 0
        if not ran:
            print(f"[probe] launch_match failed rc={proc.returncode}; wrote partial report", file=sys.stderr)
    write_probe_files(log_dir, out)
    write_summary(out, ran, log_dir)
    print(f"summary={out / 'summary.md'}")
    return 0 if ran or args.skip_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
