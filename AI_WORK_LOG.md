# AI Work Log

## 2026-05-27

- Read the local THUAI9 rule document at `docs/规则.md`.
- Read the Python API entry notes in `docs/THUAI9_API接口文档_for_python.md`.
- Chose the Python player scaffold at `CAPI/python/PyAPI/AI.py` for the first AI version.
- Implemented a baseline economy-first AI:
  - Team process recruits one Drone, one Robot, and one AutonomousCar.
  - Team process attempts economy and mobility tech upgrades.
  - Team process produces Semiconductor, Medicine, or Toys depending on material.
  - Character processes scan the map for resources, compute centers, markets, and factories.
  - Drone and Robot prioritize unowned compute centers, then harvest resources.
  - AutonomousCar harvests and helps with product transport.
  - Units load produced goods at the friendly factory and sell them at the best visible market.
  - Units attack visible enemies in range before economic work.
  - Movement uses a small A* pathfinder over passable Space/Bush cells and moves toward an adjacent interaction cell.
- Verified `CAPI/python/PyAPI/AI.py` with `python -m py_compile`.

## Known limitations

- The strategy is intentionally conservative and does not coordinate target assignment between units.
- Combat is opportunistic only; it does not raid enemy factories or retreat low-health units.
- Market choice prefers larger market type and distance, but does not yet evaluate live per-good prices.
- Product loading probes goods types because the character API does not expose factory inventory directly through the unit state.

## 2026-05-27 RL copy

- Added `CAPI/python/PyAPI/AI_RL.py` as a second AI module without replacing the first version.
- The RL copy subclasses the baseline AI and adds trainable tabular Q-learning for high-level team and character decisions.
- It uses no extra dependencies and persists learned tables beside the module:
  - `rl_team_qtable.json`
  - `rl_character_qtable_p<playerID>.json`
- Environment variables:
  - `THUAI9_RL_TRAIN=1` enables online learning and Q-table saving.
  - `THUAI9_RL_TRAIN=0` disables training and only uses the loaded policy plus heuristic fallback.
  - `THUAI9_RL_EPSILON`, `THUAI9_RL_ALPHA`, and `THUAI9_RL_GAMMA` control exploration, learning rate, and discount.
- To run it, set the AI module to `PyAPI.AI_RL`, for example with `ACTIVE_AI_MODULE=PyAPI.AI_RL`.

## 2026-05-27 Linux launcher

- Added `start_thuai9_python_1team.sh` because the existing Python one-team launcher was Windows-only.
- The Linux launcher builds the server, generates Python proto files, starts a two-team server, and starts one RL/baseline active team plus one idle dummy team.
- It defaults to headless mode (`START_UI=0`) for SSH/server training; set `START_UI=1` to also launch Avalonia UI on a desktop Linux session.

## 2026-05-27 PvE RL framework

- Read the PvE framework under `logic/pve` and chose it as the fast-training sandbox before mapping policies back to real CAPI.
- Added `logic/pve/our_agent` with:
  - `agent.py`: official-evaluator-compatible masked Double-DQN agent.
  - `train.py`: single-run training entry.
  - `evaluate.py`: local multi-seed evaluator.
  - `make_submission.py`: submission directory builder.
  - `run_4gpu_training.sh`: four-worker overnight launcher.
  - `README.md`: workflow documentation.
- Added heuristic-guided warm start using only public observations and `action_masks()`, so early training produces meaningful economy-chain experience.
- Installed PvE dependencies from `logic/pve/requirements.txt`.
- Verified:
  - `python -m pytest tests/ -q` passed 29 tests.
  - Python syntax checks passed for `our_agent`.
  - A 2000-step easy smoke run produced `runs/smoke_prior/model.pt`.
  - `official_evaluator.py` loaded the generated submission and produced a positive easy score.
- Current machine note: this shell reports `torch.cuda.is_available() == False`, so the four-GPU launcher is ready for a GPU-visible node but was not started here.

## 2026-05-28 Environment and CUDA Training Commands

Recommended route: use a fresh conda environment and install PyTorch CUDA wheels. A full system CUDA Toolkit is only needed if we need `nvcc`; PyTorch training itself only needs a working NVIDIA driver plus the PyTorch CUDA runtime.

### 0. Check GPU driver

```bash
nvidia-smi
```

If `nvidia-smi` is missing on Ubuntu 22.04, install a driver and reboot:

```bash
sudo apt update
sudo apt install -y ubuntu-drivers-common
ubuntu-drivers devices
sudo ubuntu-drivers autoinstall
sudo reboot
```

### 1. Create conda environment

```bash
conda create -n thuai9-pve python=3.11 -y
conda activate thuai9-pve
python -m pip install --upgrade pip setuptools wheel
```

### 2. Install PyTorch with CUDA runtime

Use the PyTorch official selector if this command becomes stale. Current recommended CUDA wheel target:

```bash
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

Verify:

```bash
python - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
print("device count:", torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    print(i, torch.cuda.get_device_name(i))
PY
```

### 3. Optional: install system CUDA Toolkit

Only do this if we need `nvcc` or native CUDA compilation. For Ubuntu 22.04, install NVIDIA's CUDA apt keyring and the CUDA 12.8 toolkit:

```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
rm cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install -y cuda-toolkit-12-8
```

Add CUDA Toolkit binaries for the current shell:

```bash
export CUDA_HOME=/usr/local/cuda-12.8
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
nvcc --version
```

### 4. Install PvE dependencies

```bash
cd ~/THUAI9/logic/pve
python -m pip install -r requirements.txt
python -m pytest tests/ -q
```

### 5. Smoke train

```bash
cd ~/THUAI9/logic/pve
python -m our_agent.train \
    --config easy \
    --timesteps 2000 \
    --seed 3 \
    --device cuda:0 \
    --save-dir runs/smoke_cuda \
    --learning-starts 100 \
    --batch-size 32 \
    --log-every 1000 \
    --save-every 1000
```

Evaluate smoke model:

```bash
python -m our_agent.evaluate \
    --model runs/smoke_cuda/model.pt \
    --config easy \
    --episodes 5 \
    --seeds 0 1
```

### 6. Four-GPU overnight training

```bash
cd ~/THUAI9/logic/pve
GPU_IDS="0 1 2 3" \
CONFIG=hard \
TIMESTEPS=5000000 \
BASE_SEED=20260528 \
PYTHON_EXE="$(which python)" \
SAVE_EVERY=1000000 \
LOG_EVERY=50000 \
LEARNING_STARTS=50000 \
BATCH_SIZE=512 \
BUFFER_CAPACITY=1000000 \
EPSILON_DECAY=3000000 \
HEURISTIC_DECAY=4000000 \
HEURISTIC_END=0.02 \
bash our_agent/run_4gpu_training.sh
```

This is 5,000,000 steps per GPU worker, so four workers produce about 20,000,000 total environment steps. The trainer overwrites each worker's `model.pt` instead of writing a new checkpoint file every save. `SAVE_EVERY=1000000` is enough for overnight training without unnecessary disk writes.

Monitor:

```bash
tail -f runs/our_agent_*/logs/*.log
```

Stop all workers for a run:

```bash
kill $(cat runs/our_agent_*/logs/*.pid)
```

### 7. Pick and package a model

```bash
cd ~/THUAI9/logic/pve
python -m our_agent.evaluate \
    --model runs/<run_name>/<worker_dir>/model.pt \
    --config hard \
    --episodes 100 \
    --seeds 0 42 123 999

python -m our_agent.make_submission \
    --model runs/<run_name>/<worker_dir>/model.pt \
    --output submission/our_agent

python official_evaluator.py \
    --submission submission/our_agent \
    --config hard \
    --episodes 200 \
    --seeds 0 42 123 999 7777
```

## 2026-05-28 Training Utilization Notes

- Observed PvE DQN workers using low GPU memory/utilization because the bottleneck is mostly serial Python environment stepping, not matrix multiplication.
- Updated `our_agent/agent.py` training logs to include `speed=<steps/s>` and `eta=<hours>` at each `LOG_EVERY` interval.
- Updated `our_agent/run_4gpu_training.sh` to support `WORKERS_PER_GPU`, so we can run more independent workers per GPU if CPU/RAM are available.
- Recommended throughput scaling:
  - Use all visible GPUs with `GPU_IDS="0 1 2 3 4 5 6 7"` if available.
  - If each GPU stays around 10% utilization, try `WORKERS_PER_GPU=2`.
  - Keep total intended samples in mind: total steps = `num_gpus * WORKERS_PER_GPU * TIMESTEPS`.
