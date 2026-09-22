#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C29_content_access_risk_projected — permutation-invariant teacher/student scaffold.

Training objective is constrained/risk-aware and INDEPENDENT of frozen U_eval.
U_eval = clip(0.25 Ro + 0.60 Rq - 0.15 Rb, 0, 1) remains evaluation-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class C29ModelConfig:
    user_in_dim: int = 16
    content_in_dim: int = 12
    global_in_dim: int = 10
    latent: int = 128  # teacher; student uses smaller
    n_groups: int = 3
    dropout: float = 0.05


class DeepSetsEncoder(nn.Module):
    def __init__(self, in_dim: int, latent: int, dropout: float = 0.05):
        super().__init__()
        self.phi = nn.Sequential(
            nn.Linear(in_dim, latent),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(latent, latent),
            nn.ReLU(),
        )
        self.rho = nn.Sequential(
            nn.Linear(latent, latent),
            nn.ReLU(),
            nn.Linear(latent, latent),
        )

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        # x: [B, N, D]
        h = self.phi(x)
        if mask is not None:
            h = h * mask.unsqueeze(-1)
            denom = mask.sum(dim=1, keepdim=True).clamp_min(1.0)
            pooled = h.sum(dim=1) / denom
        else:
            pooled = h.mean(dim=1)
        return self.rho(pooled)


class C29Controller(nn.Module):
    """Factorized heads A–D over DeepSets user + content + global encoders."""

    def __init__(self, cfg: C29ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.user_enc = DeepSetsEncoder(cfg.user_in_dim, cfg.latent, cfg.dropout)
        self.content_enc = nn.Sequential(
            nn.Linear(cfg.content_in_dim, cfg.latent),
            nn.ReLU(),
            nn.Linear(cfg.latent, cfg.latent),
            nn.ReLU(),
        )
        self.global_enc = nn.Sequential(
            nn.Linear(cfg.global_in_dim, cfg.latent),
            nn.ReLU(),
            nn.Linear(cfg.latent, cfg.latent),
            nn.ReLU(),
        )
        mix = cfg.latent * 3
        self.shared = nn.Sequential(nn.Linear(mix, cfg.latent), nn.ReLU())
        # Head A: per-user group logits (broadcast shared + user residual)
        self.user_res = nn.Linear(cfg.user_in_dim, cfg.latent)
        self.head_group = nn.Linear(cfg.latent * 2, cfg.n_groups)
        # Head B: base representation per group (n_groups logits over 3 base tiers)
        self.head_base_rep = nn.Linear(cfg.latent, cfg.n_groups * 3)
        # Head C: per-user upgrade score
        self.head_upgrade = nn.Linear(cfg.latent * 2, 1)
        # Head D: congestion-price / safety-margin proposal in (0,1) via sigmoid scale
        self.head_price = nn.Linear(cfg.latent, 2)
        # value / risk heads for distillation
        self.head_value = nn.Linear(cfg.latent, 1)
        self.head_cvar = nn.Linear(cfg.latent, 1)

    def forward(
        self,
        user_feats: torch.Tensor,
        content_feats: torch.Tensor,
        global_feats: torch.Tensor,
        user_mask: Optional[torch.Tensor] = None,
    ) -> dict[str, torch.Tensor]:
        # user_feats: [B,N,Du]
        u_set = self.user_enc(user_feats, user_mask)
        c = self.content_enc(content_feats)
        g = self.global_enc(global_feats)
        shared = self.shared(torch.cat([u_set, c, g], dim=-1))  # [B,L]
        # per-user
        ure = self.user_res(user_feats)  # [B,N,L]
        shared_exp = shared.unsqueeze(1).expand(-1, user_feats.size(1), -1)
        u_cat = torch.cat([shared_exp, ure], dim=-1)
        group_logits = self.head_group(u_cat)  # [B,N,K]
        upgrade_logit = self.head_upgrade(u_cat).squeeze(-1)  # [B,N]
        base_rep = self.head_base_rep(shared).view(-1, self.cfg.n_groups, 3)
        price = torch.sigmoid(self.head_price(shared))  # [B,2] -> margin, price scale
        return {
            "group_logits": group_logits,
            "upgrade_logit": upgrade_logit,
            "base_rep_logits": base_rep,
            "price_params": price,
            "value": self.head_value(shared).squeeze(-1),
            "cvar": self.head_cvar(shared).squeeze(-1),
            "shared": shared,
        }


def build_teacher() -> C29Controller:
    return C29Controller(C29ModelConfig(latent=128))


def build_student() -> C29Controller:
    return C29Controller(C29ModelConfig(latent=64))


def distillation_loss(teacher_out: dict, student_out: dict, T: float = 2.0) -> torch.Tensor:
    """Match action distributions + value/risk."""
    loss = F.kl_div(
        F.log_softmax(student_out["group_logits"] / T, dim=-1),
        F.softmax(teacher_out["group_logits"].detach() / T, dim=-1),
        reduction="batchmean",
    ) * (T * T)
    loss = loss + F.binary_cross_entropy_with_logits(
        student_out["upgrade_logit"], torch.sigmoid(teacher_out["upgrade_logit"].detach())
    )
    loss = loss + F.mse_loss(student_out["value"], teacher_out["value"].detach())
    loss = loss + F.mse_loss(student_out["cvar"], teacher_out["cvar"].detach())
    return loss


if __name__ == "__main__":
    B, N = 2, 20
    m = build_teacher()
    out = m(torch.randn(B, N, 16), torch.randn(B, 12), torch.randn(B, 10))
    assert out["group_logits"].shape == (B, N, 3)
    s = build_student()
    print("C29 scaffold OK", float(distillation_loss(out, s(torch.randn(B, N, 16), torch.randn(B, 12), torch.randn(B, 10)))))
