from __future__ import annotations

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


if nn is not None:
    class THUAI9ActorCritic(nn.Module):
        def __init__(self, obs_dim: int = 64, action_dim: int = 16, hidden_dim: int = 128, use_gru: bool = False):
            super().__init__()
            self.obs_dim = obs_dim
            self.action_dim = action_dim
            self.use_gru = use_gru
            self.encoder = nn.Sequential(
                nn.Linear(obs_dim, hidden_dim), nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim), nn.ReLU(),
            )
            self.gru = nn.GRUCell(hidden_dim, hidden_dim) if use_gru else None
            self.actor = nn.Linear(hidden_dim, action_dim)
            self.critic = nn.Linear(hidden_dim, 1)

        def forward(self, obs, hidden=None, action_mask=None):
            x = self.encoder(obs)
            if self.gru is not None:
                if hidden is None:
                    hidden = torch.zeros(obs.shape[0], x.shape[-1], device=obs.device)
                x = self.gru(x, hidden)
                hidden = x
            logits = self.actor(x)
            if action_mask is not None:
                mask = action_mask.bool()
                logits = logits.masked_fill(~mask, -1e9)
            value = self.critic(x).squeeze(-1)
            return logits, value, hidden

    class THUAI9MAPPO(nn.Module):
        def __init__(self, obs_dim: int = 64, state_dim: int = 64, action_dim: int = 16, hidden_dim: int = 128):
            super().__init__()
            self.obs_dim = obs_dim
            self.state_dim = state_dim
            self.action_dim = action_dim
            self.actor_body = nn.Sequential(nn.Linear(obs_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, hidden_dim), nn.ReLU())
            self.actor = nn.Linear(hidden_dim, action_dim)
            self.critic_body = nn.Sequential(nn.Linear(state_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, hidden_dim), nn.ReLU())
            self.critic = nn.Linear(hidden_dim, 1)

        def forward(self, obs, state=None, action_mask=None):
            x = self.actor_body(obs)
            logits = self.actor(x)
            if action_mask is not None:
                logits = logits.masked_fill(~action_mask.bool(), -1e9)
            critic_in = obs if state is None else state
            value = self.critic(self.critic_body(critic_in)).squeeze(-1)
            return logits, value, None

    THUAI9PolicyNet = THUAI9ActorCritic
else:
    class THUAI9ActorCritic:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch is required")

    THUAI9PolicyNet = THUAI9ActorCritic
    THUAI9MAPPO = THUAI9ActorCritic
