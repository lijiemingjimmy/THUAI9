from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import shutil
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PY_ROOT = REPO_ROOT / "CAPI" / "python"
SERVER_DIR = REPO_ROOT / "logic" / "Server"
SERVER_PROJ = SERVER_DIR / "Server.csproj"


def wait_port(host: str, port: int, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"server did not listen on {host}:{port}")


def start_process(cmd: List[str], cwd: Path, env: Dict[str, str], log_file: Path) -> subprocess.Popen:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    f = log_file.open("w", encoding="utf-8")
    return subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=f, stderr=subprocess.STDOUT, text=True, start_new_session=True)


def terminate_all(processes: List[subprocess.Popen]) -> None:
    for proc in processes:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                proc.terminate()
    deadline = time.time() + 8
    for proc in processes:
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.2)
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch one THUAI9 PvP match with Python agents.")
    parser.add_argument("--team-count", type=int, default=2, choices=[2, 4])
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--server-ip", default="127.0.0.1")
    parser.add_argument("--result", type=Path, default=Path("outputs/rl_pvp/results/smoke_result.json"))
    parser.add_argument("--replay", type=Path, default=Path("outputs/rl_pvp/replays/smoke"))
    parser.add_argument("--log-dir", type=Path, default=Path("outputs/rl_pvp/logs/smoke"))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-proto", action="store_true")
    parser.add_argument("--seed", type=int, default=None)
    for i in range(4):
        parser.add_argument(f"--team{i}-mode", default="rule" if i == 0 else "random")
        parser.add_argument(f"--team{i}-checkpoint", default="")
    parser.add_argument("--policy-deterministic", default="1")
    args = parser.parse_args()

    result = args.result if args.result.is_absolute() else REPO_ROOT / args.result
    replay = args.replay if args.replay.is_absolute() else REPO_ROOT / args.replay
    log_dir = args.log_dir if args.log_dir.is_absolute() else REPO_ROOT / args.log_dir
    result.parent.mkdir(parents=True, exist_ok=True)
    replay.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    env_base = os.environ.copy()
    env_base["PYTHONPATH"] = os.pathsep.join([str(PY_ROOT), str(PY_ROOT / "proto"), env_base.get("PYTHONPATH", "")])
    env_base["SERVER_PORT"] = str(args.port)
    env_base["THUAI9_LOG_DIR"] = str(log_dir / "agent_jsonl")
    if args.seed is not None:
        env_base["PYTHONHASHSEED"] = str(args.seed)

    if shutil.which("dotnet") is None:
        print("[launch_match] ERROR: dotnet not found in PATH; install .NET SDK or export PATH to dotnet before launching Server", file=sys.stderr)
        print(f"logs={log_dir}", file=sys.stderr)
        return 1
    if shutil.which(args.python) is None and not Path(args.python).exists():
        print(f"[launch_match] ERROR: python not found: {args.python}", file=sys.stderr)
        return 1

    processes: List[subprocess.Popen] = []
    try:
        if not args.skip_build:
            subprocess.run(["dotnet", "build", str(SERVER_PROJ)], cwd=str(REPO_ROOT), check=True, timeout=180)
        if not args.skip_proto:
            subprocess.run([args.python, "-m", "pip", "install", "-r", "requirements.txt"], cwd=str(PY_ROOT), check=True, timeout=180)
            subprocess.run(["bash", "generate_proto.sh"], cwd=str(PY_ROOT), check=True, timeout=180)
        server_cmd = [
            "dotnet", "run", "--no-build", "--", "--port", str(args.port), "--teamCount", str(args.team_count),
            "--gameTimeInSecond", str(args.duration), "--resultFileName", str(result), "--fileName", str(replay),
        ]
        processes.append(start_process(server_cmd, SERVER_DIR, env_base, log_dir / "server.log"))
        wait_port(args.server_ip, args.port, 120)
        for team in range(1, args.team_count + 1):
            mode = getattr(args, f"team{team-1}_mode")
            env = env_base.copy()
            env["THUAI9_AGENT_MODE"] = mode
            env["THUAI9_TEAM_ID"] = str(team)
            env["THUAI9_POLICY_DETERMINISTIC"] = str(args.policy_deterministic)
            checkpoint = getattr(args, f"team{team-1}_checkpoint")
            if checkpoint:
                ckpt_path = Path(checkpoint)
                env["THUAI9_POLICY_CHECKPOINT"] = str(ckpt_path if ckpt_path.is_absolute() else REPO_ROOT / ckpt_path)
            cmd = [args.python, "-m", "PyAPI.main", "-t", str(team), "-p", "0", "-I", args.server_ip, "-P", str(args.port), "--aiModule", "PyAPI.AI", "-d"]
            processes.append(start_process(cmd, PY_ROOT, env, log_dir / f"team{team}-0.log"))
        timeout = args.duration + 90
        server = processes[0]
        try:
            server.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"server did not exit after {timeout}s")
        if not result.exists():
            raise RuntimeError(f"server exited but result file was not created: {result}")
        print(f"result={result}")
        print(f"logs={log_dir}")
        return 0
    except Exception as exc:
        print(f"[launch_match] ERROR: {exc}", file=sys.stderr)
        print(f"logs={log_dir}", file=sys.stderr)
        return 1
    finally:
        terminate_all(processes)


if __name__ == "__main__":
    raise SystemExit(main())
