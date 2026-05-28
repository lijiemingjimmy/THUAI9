#!/usr/bin/env bash

set -euo pipefail

CONFIG="${CONFIG:-hard}"
TIMESTEPS="${TIMESTEPS:-2000000}"
BASE_SEED="${BASE_SEED:-20260527}"
RUN_ROOT="${RUN_ROOT:-runs/our_agent_$(date +%Y%m%d_%H%M%S)}"
PYTHON_EXE="${PYTHON_EXE:-python}"
GPU_IDS="${GPU_IDS:-0 1 2 3}"
WORKERS_PER_GPU="${WORKERS_PER_GPU:-1}"
LOG_EVERY="${LOG_EVERY:-50000}"
SAVE_EVERY="${SAVE_EVERY:-500000}"
LEARNING_STARTS="${LEARNING_STARTS:-50000}"
BATCH_SIZE="${BATCH_SIZE:-512}"
BUFFER_CAPACITY="${BUFFER_CAPACITY:-1000000}"
EPSILON_DECAY="${EPSILON_DECAY:-3000000}"
HEURISTIC_DECAY="${HEURISTIC_DECAY:-4000000}"
HEURISTIC_END="${HEURISTIC_END:-0.02}"
EVAL_AFTER="${EVAL_AFTER:-1}"
EVAL_EPISODES="${EVAL_EPISODES:-20}"
EVAL_SEEDS="${EVAL_SEEDS:-0 42 123 999 7777}"

mkdir -p "$RUN_ROOT/logs"

echo "[run_4gpu] config=$CONFIG timesteps=$TIMESTEPS run_root=$RUN_ROOT"
echo "[run_4gpu] gpu_ids=$GPU_IDS workers_per_gpu=$WORKERS_PER_GPU"
echo "[run_4gpu] eval_after=$EVAL_AFTER eval_episodes=$EVAL_EPISODES eval_seeds=$EVAL_SEEDS"

if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "[run_4gpu][ERROR] nvidia-smi not found. GPU training cannot start." >&2
    exit 1
fi

if ! nvidia-smi >/dev/null 2>&1; then
    echo "[run_4gpu][ERROR] nvidia-smi cannot communicate with the NVIDIA driver." >&2
    echo "[run_4gpu][ERROR] Fix the driver/session first, or run single-process CPU smoke tests." >&2
    exit 1
fi

"$PYTHON_EXE" - <<'PY'
import sys
import torch

print(f"[run_4gpu] torch={torch.__version__} cuda={torch.cuda.is_available()} devices={torch.cuda.device_count()}")
if not torch.cuda.is_available() or torch.cuda.device_count() == 0:
    sys.exit("[run_4gpu][ERROR] PyTorch cannot see CUDA devices.")
PY

index=0
worker_pids=()
for gpu in $GPU_IDS; do
    for worker in $(seq 1 "$WORKERS_PER_GPU"); do
        seed=$((BASE_SEED + index))
        save_dir="$RUN_ROOT/gpu${gpu}_w${worker}_seed${seed}"
        log_file="$RUN_ROOT/logs/gpu${gpu}_w${worker}_seed${seed}.log"
        echo "[run_4gpu] launching gpu=$gpu worker=$worker seed=$seed save=$save_dir"
        (
            CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON_EXE" -m our_agent.train \
                --config "$CONFIG" \
                --timesteps "$TIMESTEPS" \
                --seed "$seed" \
                --device cuda \
                --save-dir "$save_dir" \
                --log-every "$LOG_EVERY" \
                --save-every "$SAVE_EVERY" \
                --learning-starts "$LEARNING_STARTS" \
                --batch-size "$BATCH_SIZE" \
                --buffer-capacity "$BUFFER_CAPACITY" \
                --epsilon-decay "$EPSILON_DECAY" \
                --heuristic-decay "$HEURISTIC_DECAY" \
                --heuristic-end "$HEURISTIC_END"
        ) >"$log_file" 2>&1 &
        pid=$!
        worker_pids+=("$pid")
        echo "$pid" >"$RUN_ROOT/logs/gpu${gpu}_w${worker}_seed${seed}.pid"
        index=$((index + 1))
    done
done

echo "[run_4gpu] launched $index workers"
echo "[run_4gpu] monitor with: tail -f $RUN_ROOT/logs/*.log"
echo "[run_4gpu] stop with: kill \$(cat $RUN_ROOT/logs/*.pid)"

status=0
for pid in "${worker_pids[@]}"; do
    if ! wait "$pid"; then
        status=1
    fi
done

if [ "$status" -ne 0 ]; then
    echo "[run_4gpu][ERROR] at least one worker failed; skip auto-eval" >&2
    exit "$status"
fi

if [ "$EVAL_AFTER" != "1" ]; then
    echo "[run_4gpu] all workers finished; auto-eval disabled"
    exit 0
fi

echo "[run_4gpu] all workers finished; evaluating checkpoints"
summary="$RUN_ROOT/eval_summary.tsv"
summary_body="$RUN_ROOT/eval_summary.body.tsv"
printf "score_mean\tscore_std\tmodel\n" >"$summary"
: >"$summary_body"

for model in "$RUN_ROOT"/gpu*_w*_seed*/model.pt; do
    [ -f "$model" ] || continue
    out="${model%/model.pt}/eval.json"
    echo "[run_4gpu] eval $model"
    "$PYTHON_EXE" -m our_agent.evaluate \
        --model "$model" \
        --config "$CONFIG" \
        --episodes "$EVAL_EPISODES" \
        --seeds $EVAL_SEEDS \
        --output "$out"
    "$PYTHON_EXE" - "$out" "$model" >>"$summary_body" <<'PY'
import json
import sys

path, model = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"{data['score_mean']:.6f}\t{data['score_std']:.6f}\t{model}")
PY
done

sort -nr "$summary_body" >>"$summary"
rm -f "$summary_body"
echo "[run_4gpu] eval summary: $summary"
cat "$summary"
