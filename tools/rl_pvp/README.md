# THUAI9 RL PvP 工程入口

## 当前状态

可直接用于正式 PvP 提交的是 `CAPI/python/PyAPI/AI.py` 加 `PyAPI.rl_agent` 包：官方仍然从 `PyAPI.main` 调 `AI.CharacterPlay/TeamPlay`，agent 模式用环境变量切换。

训练/评估脚本在 `tools/rl_pvp/`，属于本地训练辅助，不需要随正式提交一起改 Server 规则。

## 依赖

官方 Python 依赖：

```bash
cd CAPI/python
python -m pip install -r requirements.txt
bash generate_proto.sh
```

Linux 下 Server 需要 `dotnet`。训练 skeleton 如需生成 PyTorch checkpoint，需要额外安装 `torch`；配置 YAML 读取优先用 `pyyaml`，没有时会用一个很小的内置 YAML parser 读取简单配置。

## 官方本地测试

仓库里实际存在这些脚本：

```bash
start_thuai9_python_1team.sh
start_thuai9_python_1team.bat
start_thuai9_python_4team.bat
```

Linux 1v1/占位队测试：

```bash
THUAI9_AGENT_MODE=rule START_UI=0 bash start_thuai9_python_1team.sh
```

Windows：

```bat
set THUAI9_AGENT_MODE=rule
start_thuai9_python_1team.bat
```

## 我们自己的 smoke test

```bash
python tools/rl_pvp/launch_match.py \
  --team-count 2 \
  --duration 120 \
  --team0-mode rule \
  --team1-mode random \
  --result outputs/rl_pvp/results/smoke_result.json \
  --log-dir outputs/rl_pvp/logs/smoke
```

验收：Server 启动，两队 `playerID=0` 连接，`BuildCharacter` 后角色进程自动拉起，比赛结束生成 result JSON，`outputs/rl_pvp/logs/.../agent_jsonl/` 下有 JSONL rollout。

如果 proto/server 已经构建过，可加：

```bash
--skip-build --skip-proto
```

## 评估

```bash
python tools/rl_pvp/evaluate.py \
  --num-games 20 \
  --team-count 2 \
  --candidate-mode rule \
  --opponent-mode random \
  --duration 180 \
  --out outputs/rl_pvp/eval/rule_vs_random.json
```

输出：summary JSON、同名 CSV、每局 result 路径、每局 log_dir、crash 统计。当前 parser 只依赖 Server 的 `{"Team 1": score}` 结果格式，字段变化时会 defensive fallback。

## rollout logs

每个队伍/角色一个 JSONL：

```text
outputs/rl_pvp/logs/<run>/agent_jsonl/team<id>_player<id>.jsonl
```

字段包含 tick、team/player、observation summary、raw action id、macro action、mask、success/failure、score、compute、material、factory HP、visible enemies、reward components。

## 训练 skeleton

PPO：

```bash
python tools/rl_pvp/evaluate.py --num-games 100 --candidate-mode rule --opponent-mode rule --duration 300
PYTHONPATH=CAPI/python:CAPI/python/proto python tools/rl_pvp/train_ppo.py \
  --config configs/rl_pvp/ppo.yaml \
  --data outputs/rl_pvp/logs/ \
  --out outputs/rl_pvp/checkpoints/ppo_skeleton.pt
```

MAPPO/self-play：

```bash
python tools/rl_pvp/train_mappo.py --config configs/rl_pvp/mappo.yaml
python tools/rl_pvp/league.py --config configs/rl_pvp/mappo.yaml
```

完整可运行：`launch_match.py`、`evaluate.py`、`parse_results.py`、`rule/random agent`、rollout logger。

Skeleton/TODO：PPO/MAPPO 目前只有数据入口、模型骨架、checkpoint placeholder、league 调度结构；还没实现真实 minibatch 更新、self-play checkpoint promotion 和 exploiters 专项奖励。

## agent 模式

```bash
THUAI9_AGENT_MODE=rule    # deterministic baseline
THUAI9_AGENT_MODE=random  # masked random/debug
THUAI9_AGENT_MODE=policy  # checkpoint 存在则 PyTorch policy，否则 fallback rule
```

可选：

```bash
THUAI9_AGENT_CONFIG=configs/rl_pvp/rule_baseline.yaml
THUAI9_DECISION_INTERVAL_MS=300
THUAI9_LOG_DIR=outputs/rl_pvp/logs/manual
THUAI9_CHECKPOINT=outputs/rl_pvp/checkpoints/policy.pt
```

## 提交边界

正式提交使用：

- `CAPI/python/PyAPI/AI.py`
- `CAPI/python/PyAPI/rl_agent/`

训练辅助使用：

- `tools/rl_pvp/`
- `configs/rl_pvp/`
- `outputs/rl_pvp/` 运行时产物，不要提交 checkpoint。


## Stage 2: 真实训练闭环

### 1. Smoke

```bash
python3 tools/rl_pvp/launch_match.py \
  --team-count 2 \
  --duration 120 \
  --team0-mode rule \
  --team1-mode random \
  --result outputs/rl_pvp/results/smoke_result.json \
  --log-dir outputs/rl_pvp/logs/smoke
```

分析 rollout：

```bash
python3 tools/rl_pvp/analyze_rollouts.py \
  --log-dir outputs/rl_pvp/logs/smoke \
  --out outputs/rl_pvp/analysis/smoke
```

输出：`summary.json`、`action_hist.csv`、`reward_components.csv`、`warnings.txt`。

### 2. Baseline regression

```bash
python3 tools/rl_pvp/evaluate.py \
  --num-games 20 \
  --team-count 2 \
  --candidate-mode rule \
  --opponent-mode random \
  --duration 180 \
  --out outputs/rl_pvp/eval/rule_vs_random.json

python3 tools/rl_pvp/evaluate.py \
  --num-games 20 \
  --team-count 2 \
  --candidate-mode rule \
  --opponent-mode rule \
  --duration 180 \
  --out outputs/rl_pvp/eval/rule_vs_rule.json
```

### 3. Collect rollout

```bash
python3 tools/rl_pvp/evaluate.py \
  --num-games 100 \
  --team-count 2 \
  --candidate-mode policy \
  --candidate-checkpoint outputs/rl_pvp/checkpoints/ppo/latest.pt \
  --opponent-mode rule \
  --duration 300 \
  --out outputs/rl_pvp/eval/collect_policy_vs_rule.json \
  --log-dir outputs/rl_pvp/logs/policy_vs_rule_round_000
```

如果 checkpoint 不存在，先用 rule warm-start：

```bash
python3 tools/rl_pvp/evaluate.py \
  --num-games 100 \
  --team-count 2 \
  --candidate-mode rule \
  --opponent-mode rule \
  --duration 300 \
  --out outputs/rl_pvp/eval/collect_rule_vs_rule.json \
  --log-dir outputs/rl_pvp/logs/rule_vs_rule_warmstart
```

### 4. Train PPO

```bash
python3 tools/rl_pvp/train_ppo.py \
  --config configs/rl_pvp/ppo.yaml \
  --data outputs/rl_pvp/logs/policy_vs_rule_round_000 \
  --out outputs/rl_pvp/checkpoints/ppo/latest.pt
```

旧 rule 日志没有 `log_prob/value` 时会走 imitation/warm-start；policy rollout 有这些字段时走 PPO clipped objective。

### 5. Evaluate policy

```bash
python3 tools/rl_pvp/evaluate.py \
  --num-games 50 \
  --team-count 2 \
  --candidate-mode policy \
  --candidate-checkpoint outputs/rl_pvp/checkpoints/ppo/latest.pt \
  --opponent-mode rule \
  --duration 300 \
  --out outputs/rl_pvp/eval/ppo_vs_rule.json
```

### 6. MAPPO / league

```bash
python3 tools/rl_pvp/train_mappo.py \
  --config configs/rl_pvp/mappo.yaml \
  --data outputs/rl_pvp/logs/rule_vs_rule_warmstart \
  --out outputs/rl_pvp/checkpoints/mappo/latest.pt

python3 tools/rl_pvp/league.py \
  --config configs/rl_pvp/mappo.yaml \
  --rounds 5 \
  --rollout-games 20 \
  --candidate outputs/rl_pvp/checkpoints/mappo/latest.pt
```

当前 MAPPO 是最小可运行版：shared actor + centralized critic，但 critic 的 centralized state 在日志无法严格对齐时使用同 team 最近 observation 近似。

### 7. Debug

```bash
THUAI9_RL_DEBUG=1 THUAI9_AGENT_MODE=rule python3 -m PyAPI.main -t 1 -p 0 -I 127.0.0.1 -P 8888
THUAI9_AGENT_MODE=policy THUAI9_POLICY_CHECKPOINT=outputs/rl_pvp/checkpoints/ppo/latest.pt THUAI9_POLICY_DETERMINISTIC=1 python3 -m PyAPI.main -t 1 -p 0 -I 127.0.0.1 -P 8888
```

### 8. 正式提交边界

正式 PvP 可提交：

```text
CAPI/python/PyAPI/AI.py
CAPI/python/PyAPI/rl_agent/
```

训练辅助：

```text
tools/rl_pvp/
configs/rl_pvp/
outputs/rl_pvp/
```

正式提交不要依赖 `outputs/rl_pvp/logs`、训练数据、大 checkpoint、Server patch、绝对路径。如果要提交 policy，放轻量文件到 `CAPI/python/PyAPI/rl_agent/checkpoints/final_policy.pt`，并通过配置或 `THUAI9_POLICY_CHECKPOINT` 指向它。
