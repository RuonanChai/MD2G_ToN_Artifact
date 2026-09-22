#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generation-2 native Rep1–9 teacher/student (command114).

Not a binary Base/Enhanced wrapper. Actions are:
  - group assignment (slow timescale prior)
  - 9-rep scores (fast representation)
  - hold / last-playable
Feasibility is applied outside the network (fail-closed projector).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class G2ModelConfig:
    user_in_dim: int = 16
    content_in_dim: int = 12
    global_in_dim: int = 10
    latent: int = 128
    n_groups: int = 3
    n_reps: int = 9
    dropout: float = 0.05


class DeepSetsEncoder(nn.Module):
    def __init__(self, in_dim: int, latent: int, dropout: float = 0.05):
        super().__init__()
        self.phi = nn.Sequential(
            nn.Linear(in_dim, latent), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(latent, latent), nn.ReLU(),
        )
        self.rho = nn.Sequential(nn.Linear(latent, latent), nn.ReLU(), nn.Linear(latent, latent))

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        h = self.phi(x)
        if mask is not None:
            h = h * mask.unsqueeze(-1)
            denom = mask.sum(dim=1, keepdim=True).clamp_min(1.0)
            pooled = h.sum(dim=1) / denom
        else:
            pooled = h.mean(dim=1)
        return self.rho(pooled)


class G2Native9RepController(nn.Module):
    def __init__(self, cfg: G2ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.user_enc = DeepSetsEncoder(cfg.user_in_dim, cfg.latent, cfg.dropout)
        self.content_enc = nn.Sequential(
            nn.Linear(cfg.content_in_dim, cfg.latent), nn.ReLU(),
            nn.Linear(cfg.latent, cfg.latent), nn.ReLU(),
        )
        self.global_enc = nn.Sequential(
            nn.Linear(cfg.global_in_dim, cfg.latent), nn.ReLU(),
            nn.Linear(cfg.latent, cfg.latent), nn.ReLU(),
        )
        self.shared = nn.Sequential(nn.Linear(cfg.latent * 3, cfg.latent), nn.ReLU())
        self.user_res = nn.Linear(cfg.user_in_dim, cfg.latent)
        mix = cfg.latent * 2
        self.head_group = nn.Linear(mix, cfg.n_groups)
        self.head_rep = nn.Linear(mix, cfg.n_reps)  # native 9-rep scores
        self.head_hold = nn.Linear(mix, 1)
        self.head_price = nn.Linear(cfg.latent, 2)
        self.head_value = nn.Linear(cfg.latent, 1)

    def forward(self, user_feats, content_feats, global_feats, user_mask=None):
        u_set = self.user_enc(user_feats, user_mask)
        c = self.content_enc(content_feats)
        g = self.global_enc(global_feats)
        shared = self.shared(torch.cat([u_set, c, g], dim=-1))
        ure = self.user_res(user_feats)
        u_cat = torch.cat([shared.unsqueeze(1).expand(-1, user_feats.size(1), -1), ure], dim=-1)
        return {
            "group_logits": self.head_group(u_cat),
            "rep_logits": self.head_rep(u_cat),
            "hold_logit": self.head_hold(u_cat).squeeze(-1),
            "price_params": torch.sigmoid(self.head_price(shared)),
            "value": self.head_value(shared).squeeze(-1),
            "shared": shared,
        }


def build_teacher() -> G2Native9RepController:
    return G2Native9RepController(G2ModelConfig(latent=128))


def build_student() -> G2Native9RepController:
    return G2Native9RepController(G2ModelConfig(latent=64, dropout=0.0))


def distillation_loss(teacher_out: dict, student_out: dict, T: float = 2.0) -> torch.Tensor:
    loss = F.kl_div(
        F.log_softmax(student_out["group_logits"] / T, dim=-1),
        F.softmax(teacher_out["group_logits"].detach() / T, dim=-1),
        reduction="batchmean",
    ) * (T * T)
    loss = loss + F.kl_div(
        F.log_softmax(student_out["rep_logits"] / T, dim=-1),
        F.softmax(teacher_out["rep_logits"].detach() / T, dim=-1),
        reduction="batchmean",
    ) * (T * T)
    loss = loss + F.binary_cross_entropy_with_logits(
        student_out["hold_logit"], torch.sigmoid(teacher_out["hold_logit"].detach())
    )
    loss = loss + F.mse_loss(student_out["value"], teacher_out["value"].detach())
    return loss
