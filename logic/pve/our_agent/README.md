# Our THUAI9 PvE RL Agent

This directory contains our trainable PvE agent framework.

## Files

- `agent.py`: official-evaluator-compatible `Agent(BaseAgent)` implementation.
- `train.py`: single-process masked Double-DQN training.
- `evaluate.py`: multi-seed local evaluation.
- `make_submission.py`: copies `agent.py` and `model.pt` into a submission directory.
- `run_4gpu_training.sh`: launches four independent overnight training workers.

## Setup

From `logic/pve`:

```bash
python -m pip install -r requirements.txt
```

## Single Run

```bash
python -m our_agent.train \
    --config hard \
    --timesteps 2000000 \
    --seed 0 \
    --device cuda:0 \
    --save-dir runs/debug
```

## Four-GPU Overnight Run

```bash
GPU_IDS="0 1 2 3" CONFIG=hard TIMESTEPS=5000000 bash our_agent/run_4gpu_training.sh
```

Each GPU trains an independent seed. With four GPUs, the default is 4 × 5,000,000 = 20,000,000 total environment steps. Pick the best final checkpoint by evaluation.
The agent uses masked Double-DQN with heuristic-guided warm start. The heuristic only reads the public observation vector and `action_masks()`, then decays during training while Q-values take over.

Overnight defaults:

- `TIMESTEPS=5000000` per worker.
- `SAVE_EVERY=1000000`; saves overwrite `model.pt` instead of creating many checkpoint files.
- `LOG_EVERY=50000`.
- `LEARNING_STARTS=50000`.
- `BATCH_SIZE=512`.
- `BUFFER_CAPACITY=1000000`.
- `EPSILON_DECAY=3000000`.
- `HEURISTIC_DECAY=4000000`.
- `HEURISTIC_END=0.02`.

## Evaluate

```bash
python -m our_agent.evaluate \
    --model runs/debug/model.pt \
    --config hard \
    --episodes 100
```

## Official Evaluator Submission

```bash
python -m our_agent.make_submission \
    --model runs/debug/model.pt \
    --output submission/our_agent

python official_evaluator.py \
    --submission submission/our_agent \
    --config hard \
    --episodes 200 \
    --seeds 0 42 123 999 7777
```

## Smoke-Tested Commands

These commands were verified locally:

```bash
python -m pytest tests/ -q
python -m our_agent.train --config easy --timesteps 2000 --seed 3 --device cpu --save-dir runs/smoke_prior --learning-starts 100 --batch-size 32
python -m our_agent.evaluate --model runs/smoke_prior/model.pt --config easy --episodes 2 --seeds 0 1
python -m our_agent.make_submission --model runs/smoke_prior/model.pt --output runs/smoke_prior_submission
python official_evaluator.py --submission runs/smoke_prior_submission --config easy --episodes 1 --seeds 0
```
