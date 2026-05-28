from __future__ import annotations

import math
import os
import random
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from GameLogic import N_ACTIONS
from RLInterfaces import BaseAgent


class AgentConfig:
    def __init__(
        self,
        hidden_dim: int = 256,
        lr: float = 1e-4,
        gamma: float = 0.99,
        batch_size: int = 256,
        buffer_capacity: int = 500_000,
        learning_starts: int = 10_000,
        train_freq: int = 4,
        target_update_freq: int = 2_000,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.05,
        epsilon_decay: int = 500_000,
        heuristic_start: float = 0.80,
        heuristic_end: float = 0.05,
        heuristic_decay: int = 800_000,
        heuristic_q_bonus: float = 2.0,
        grad_clip: float = 10.0,
        double_dqn: bool = True,
    ):
        self.hidden_dim = hidden_dim
        self.lr = lr
        self.gamma = gamma
        self.batch_size = batch_size
        self.buffer_capacity = buffer_capacity
        self.learning_starts = learning_starts
        self.train_freq = train_freq
        self.target_update_freq = target_update_freq
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.heuristic_start = heuristic_start
        self.heuristic_end = heuristic_end
        self.heuristic_decay = heuristic_decay
        self.heuristic_q_bonus = heuristic_q_bonus
        self.grad_clip = grad_clip
        self.double_dqn = double_dqn

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hidden_dim": self.hidden_dim,
            "lr": self.lr,
            "gamma": self.gamma,
            "batch_size": self.batch_size,
            "buffer_capacity": self.buffer_capacity,
            "learning_starts": self.learning_starts,
            "train_freq": self.train_freq,
            "target_update_freq": self.target_update_freq,
            "epsilon_start": self.epsilon_start,
            "epsilon_end": self.epsilon_end,
            "epsilon_decay": self.epsilon_decay,
            "heuristic_start": self.heuristic_start,
            "heuristic_end": self.heuristic_end,
            "heuristic_decay": self.heuristic_decay,
            "heuristic_q_bonus": self.heuristic_q_bonus,
            "grad_clip": self.grad_clip,
            "double_dqn": self.double_dqn,
        }


class QNetwork(nn.Module):
    def __init__(self, obs_dim: int, hidden_dim: int, n_actions: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, n_actions),
        )

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.net(obs)


class ReplayBuffer:
    def __init__(self, capacity: int):
        self.buffer: Deque[Tuple[np.ndarray, int, float, np.ndarray, bool, np.ndarray, np.ndarray]] = deque(
            maxlen=capacity
        )

    def push(
        self,
        obs: np.ndarray,
        action: int,
        reward: float,
        next_obs: np.ndarray,
        done: bool,
        mask: np.ndarray,
        next_mask: np.ndarray,
    ) -> None:
        self.buffer.append(
            (
                obs.astype(np.float32, copy=False),
                int(action),
                float(reward),
                next_obs.astype(np.float32, copy=False),
                bool(done),
                mask.astype(bool, copy=False),
                next_mask.astype(bool, copy=False),
            )
        )

    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        obs, actions, rewards, next_obs, dones, masks, next_masks = zip(*batch)
        return (
            np.stack(obs),
            np.asarray(actions, dtype=np.int64),
            np.asarray(rewards, dtype=np.float32),
            np.stack(next_obs),
            np.asarray(dones, dtype=np.float32),
            np.stack(masks),
            np.stack(next_masks),
        )

    def __len__(self) -> int:
        return len(self.buffer)


class Agent(BaseAgent):
    def __init__(
        self,
        env,
        config: Optional[AgentConfig] = None,
        device: Optional[str] = None,
        seed: int = 0,
    ):
        super().__init__(env)
        self.config = config or AgentConfig()
        self.obs_dim = int(env.observation_space.shape[0])
        self.n_actions = int(N_ACTIONS)
        self.device = torch.device(device or self._default_device())
        self.rng = random.Random(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

        self.q_net = QNetwork(self.obs_dim, self.config.hidden_dim, self.n_actions).to(self.device)
        self.target_net = QNetwork(self.obs_dim, self.config.hidden_dim, self.n_actions).to(self.device)
        self.target_net.load_state_dict(self.q_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.AdamW(self.q_net.parameters(), lr=self.config.lr)
        self.loss_fn = nn.SmoothL1Loss()
        self.replay = ReplayBuffer(self.config.buffer_capacity)

        self.total_steps = 0
        self.train_steps = 0
        self.epsilon = self.config.epsilon_start

    def get_action(self, observation: np.ndarray) -> int:
        mask = self.env.action_masks()
        valid_actions = np.flatnonzero(mask)
        if len(valid_actions) == 0:
            return 0

        heuristic = self._heuristic_action(observation, mask)
        if heuristic is not None and self.rng.random() < self._heuristic_rate():
            return heuristic

        if self.rng.random() < self.epsilon:
            return int(self.rng.choice(valid_actions.tolist()))

        q_values = self._q_values(observation)
        if heuristic is not None:
            q_values[heuristic] += self.config.heuristic_q_bonus
        q_values[~mask] = -1e9
        return int(np.argmax(q_values))

    def train(self, total_timesteps: int, **kwargs) -> Dict[str, Any]:
        log_every = int(kwargs.get("log_every", 10_000))
        save_every = int(kwargs.get("save_every", 100_000))
        save_path = kwargs.get("save_path")
        eval_epsilon = float(kwargs.get("eval_epsilon", self.config.epsilon_end))

        obs = self.reset()
        episode_reward = 0.0
        episode_score = 0.0
        episode_count = 0
        reward_window: Deque[float] = deque(maxlen=50)
        score_window: Deque[float] = deque(maxlen=50)
        started_at = time.time()

        for _ in range(total_timesteps):
            mask = self.env.action_masks().copy()
            action = self.get_action(obs)
            next_obs, reward, terminated, truncated, info = self.step(action)
            done = terminated or truncated
            next_mask = self.env.action_masks().copy()

            self.replay.push(obs, action, reward, next_obs, done, mask, next_mask)
            episode_reward += reward
            episode_score = float(info.get("score", episode_score))
            self.total_steps += 1
            self._update_epsilon()

            if (
                len(self.replay) >= self.config.learning_starts
                and self.total_steps % self.config.train_freq == 0
            ):
                self._train_step()

            if self.total_steps % self.config.target_update_freq == 0:
                self.target_net.load_state_dict(self.q_net.state_dict())

            obs = next_obs
            if done:
                reward_window.append(episode_reward)
                score_window.append(episode_score)
                episode_count += 1
                episode_reward = 0.0
                episode_score = 0.0
                obs = self.reset()

            if log_every > 0 and self.total_steps % log_every == 0:
                mean_reward = float(np.mean(reward_window)) if reward_window else 0.0
                mean_score = float(np.mean(score_window)) if score_window else 0.0
                elapsed = max(1e-6, time.time() - started_at)
                steps_per_second = self.total_steps / elapsed
                remaining = max(0, total_timesteps - self.total_steps)
                eta_seconds = remaining / max(1e-6, steps_per_second)
                print(
                    f"step={self.total_steps:,} episodes={episode_count} "
                    f"eps={self.epsilon:.3f} buffer={len(self.replay):,} "
                    f"train={self.train_steps:,} reward50={mean_reward:.3f} "
                    f"score50={mean_score:.1f} "
                    f"speed={steps_per_second:.1f} steps/s eta={eta_seconds / 3600:.2f}h",
                    flush=True,
                )

            if save_path and save_every > 0 and self.total_steps % save_every == 0:
                self.save(save_path)

        old_epsilon = self.epsilon
        self.epsilon = eval_epsilon
        self.epsilon = old_epsilon

        return {
            "total_timesteps": total_timesteps,
            "agent_total_steps": self.total_steps,
            "episodes": episode_count,
            "epsilon": self.epsilon,
            "buffer_size": len(self.replay),
            "train_steps": self.train_steps,
            "mean_reward_50": float(np.mean(reward_window)) if reward_window else 0.0,
            "mean_score_50": float(np.mean(score_window)) if score_window else 0.0,
        }

    def move_to_device(self, device: str) -> None:
        self.device = torch.device(device)
        self.q_net.to(self.device)
        self.target_net.to(self.device)
        for state in self.optimizer.state.values():
            for key, value in state.items():
                if torch.is_tensor(value):
                    state[key] = value.to(self.device)

    def save(self, path: str) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        torch.save(
            {
                "config": self.config.to_dict(),
                "obs_dim": self.obs_dim,
                "n_actions": self.n_actions,
                "q_net": self.q_net.state_dict(),
                "target_net": self.target_net.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "epsilon": self.epsilon,
                "total_steps": self.total_steps,
                "train_steps": self.train_steps,
            },
            path,
        )

    @classmethod
    def load(cls, path: str, env) -> "Agent":
        data = torch.load(path, map_location="cpu", weights_only=False)
        config = AgentConfig(**data.get("config", {}))
        agent = cls(env, config=config, device="cpu")
        agent.q_net.load_state_dict(data["q_net"])
        agent.target_net.load_state_dict(data.get("target_net", data["q_net"]))
        try:
            agent.optimizer.load_state_dict(data["optimizer"])
        except KeyError:
            pass
        agent.epsilon = 0.0
        agent.total_steps = int(data.get("total_steps", 0))
        agent.train_steps = int(data.get("train_steps", 0))
        agent.q_net.eval()
        agent.target_net.eval()
        return agent

    def _train_step(self) -> None:
        obs, actions, rewards, next_obs, dones, _masks, next_masks = self.replay.sample(
            self.config.batch_size
        )
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        actions_t = torch.as_tensor(actions, dtype=torch.int64, device=self.device).unsqueeze(1)
        rewards_t = torch.as_tensor(rewards, dtype=torch.float32, device=self.device).unsqueeze(1)
        next_obs_t = torch.as_tensor(next_obs, dtype=torch.float32, device=self.device)
        dones_t = torch.as_tensor(dones, dtype=torch.float32, device=self.device).unsqueeze(1)
        next_masks_t = torch.as_tensor(next_masks, dtype=torch.bool, device=self.device)

        current_q = self.q_net(obs_t).gather(1, actions_t)

        with torch.no_grad():
            if self.config.double_dqn:
                next_q_online = self.q_net(next_obs_t)
                next_q_online = next_q_online.masked_fill(~next_masks_t, -1e9)
                next_actions = next_q_online.argmax(dim=1, keepdim=True)
                next_q_target = self.target_net(next_obs_t).gather(1, next_actions)
            else:
                next_q_target_all = self.target_net(next_obs_t)
                next_q_target_all = next_q_target_all.masked_fill(~next_masks_t, -1e9)
                next_q_target = next_q_target_all.max(dim=1, keepdim=True).values
            target_q = rewards_t + self.config.gamma * (1.0 - dones_t) * next_q_target

        loss = self.loss_fn(current_q, target_q)
        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(self.q_net.parameters(), self.config.grad_clip)
        self.optimizer.step()
        self.train_steps += 1

    def _q_values(self, observation: np.ndarray) -> np.ndarray:
        obs_t = torch.as_tensor(observation, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            return self.q_net(obs_t).detach().cpu().numpy().reshape(-1)

    def _update_epsilon(self) -> None:
        progress = min(1.0, self.total_steps / max(1, self.config.epsilon_decay))
        cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
        self.epsilon = self.config.epsilon_end + (
            self.config.epsilon_start - self.config.epsilon_end
        ) * cosine

    def _heuristic_rate(self) -> float:
        if self.epsilon <= 0.0:
            return 0.0
        progress = min(1.0, self.total_steps / max(1, self.config.heuristic_decay))
        return self.config.heuristic_end + (
            self.config.heuristic_start - self.config.heuristic_end
        ) * (1.0 - progress)

    def _heuristic_action(self, obs: np.ndarray, mask: np.ndarray) -> Optional[int]:
        for action in (6, 7, 8, 9, 10):
            if mask[action]:
                return action
        for action in (18, 13, 14, 17, 16, 15, 12, 11, 19):
            if mask[action]:
                return action
        for action in (21, 22, 24, 27, 23, 20, 25, 26):
            if mask[action]:
                return action

        product_load = float(np.sum(obs[4:9]))
        raw_load = float(obs[3])
        factory_product_stock = float(np.sum(obs[16:21]))
        factory_raw_stock = float(obs[15])

        if product_load > 0.01:
            target = self._nearest_market_delta(obs)
            return self._move_towards_delta(target, mask)
        if raw_load > 0.01 or factory_product_stock > 0.001 or factory_raw_stock > 0.02:
            return self._move_towards_delta((-float(obs[0]), -float(obs[1])), mask)

        center = self._nearest_closed_center_delta(obs)
        if center is not None:
            move = self._move_towards_delta(center, mask)
            if move is not None:
                return move

        resource = self._nearest_resource_delta(obs)
        if resource is not None:
            move = self._move_towards_delta(resource, mask)
            if move is not None:
                return move

        return 0 if mask[0] else None

    def _nearest_market_delta(self, obs: np.ndarray) -> Optional[Tuple[float, float]]:
        best = None
        best_dist = float("inf")
        for i in range(4):
            base = 46 + i * 7
            dx = float(obs[base])
            dy = float(obs[base + 1])
            if dx == 0.0 and dy == 0.0:
                continue
            dist = abs(dx) + abs(dy)
            if dist < best_dist:
                best = (dx, dy)
                best_dist = dist
        return best

    def _nearest_resource_delta(self, obs: np.ndarray) -> Optional[Tuple[float, float]]:
        best = None
        best_dist = float("inf")
        for i in range(4):
            base = 22 + i * 3
            dx = float(obs[base])
            dy = float(obs[base + 1])
            stock = float(obs[base + 2])
            if stock <= 0.0:
                continue
            dist = abs(dx) + abs(dy)
            if dist < best_dist:
                best = (dx, dy)
                best_dist = dist
        return best

    def _nearest_closed_center_delta(self, obs: np.ndarray) -> Optional[Tuple[float, float]]:
        best = None
        best_dist = float("inf")
        for i in range(3):
            base = 34 + i * 4
            dx = float(obs[base])
            dy = float(obs[base + 1])
            is_open = float(obs[base + 2])
            if is_open >= 0.5 or (dx == 0.0 and dy == 0.0):
                continue
            dist = abs(dx) + abs(dy)
            if dist < best_dist:
                best = (dx, dy)
                best_dist = dist
        return best

    def _move_towards_delta(
        self, target: Optional[Tuple[float, float]], mask: np.ndarray
    ) -> Optional[int]:
        if target is None:
            return None
        dx, dy = target
        primary = None
        secondary = None
        if abs(dx) >= abs(dy):
            primary = 2 if dx > 0 else 1
            secondary = 4 if dy > 0 else 3
        else:
            primary = 4 if dy > 0 else 3
            secondary = 2 if dx > 0 else 1
        if primary is not None and mask[primary]:
            return primary
        if secondary is not None and mask[secondary]:
            return secondary
        for action in (1, 2, 3, 4):
            if mask[action]:
                return action
        return None

    def _default_device(self) -> str:
        return "cuda" if torch.cuda.is_available() else "cpu"
