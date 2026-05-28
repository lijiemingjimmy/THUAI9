from __future__ import annotations

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


if nn is not None:
    class THUAI9PolicyNet(nn.Module):
        def __init__(self, obs_dim: int = 64, action_dim: int = 16, hidden_dim: int = 128, use_gru: bool = False):
            super().__init__()
            self.obs_dim = obs_dim
            self.action_dim = action_dim
            self.use_gru = use_gru
            self.encoder = nn.Sequential(nn.Linear(obs_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, hidden_dim), nn.ReLU())
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
                logits = logits.masked_fill(~action_mask, -1e9)
            value = self.critic(x).squeeze(-1)
            return logits, value, hidden
else:
    class THUAI9PolicyNet:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch is required for THUAI9PolicyNet")
