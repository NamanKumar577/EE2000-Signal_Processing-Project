"""
src/models/fecg_unet.py
──────────────────────────────────────────────────────────────────────────────
Deep 1D Convolutional U-Net for Non-Invasive Fetal ECG Waveform Reconstruction.
Optimized for training on GPU (ASUS TUF CUDA / Apple Silicon MPS / CPU).

Architecture:
  - Multi-Scale 1D Encoder (Downsampling path capturing wide maternal waves)
  - Latent Bottleneck with expanded receptive field
  - Multi-Scale 1D Decoder with Skip Connections (Preserves sharp fetal QRS temporal resolution)
  - Numerically Stable Composite Waveform Loss (Smooth L1 + Pearson Correlation)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class DoubleConv1D(nn.Module):
    """(Convolution1D => BatchNorm => LeakyReLU) * 2"""
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 11):
        super().__init__()
        padding = kernel_size // 2
        self.net = nn.Sequential(
            nn.Conv1d(in_channels, out_channels, kernel_size=kernel_size, padding=padding, bias=False),
            nn.BatchNorm1d(out_channels),
            nn.LeakyReLU(0.1, inplace=True),
            nn.Conv1d(out_channels, out_channels, kernel_size=kernel_size, padding=padding, bias=False),
            nn.BatchNorm1d(out_channels),
            nn.LeakyReLU(0.1, inplace=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class DownBlock1D(nn.Module):
    """Downscaling with MaxPool1D then DoubleConv1D"""
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 11):
        super().__init__()
        self.pool = nn.MaxPool1d(kernel_size=2, stride=2)
        self.conv = DoubleConv1D(in_channels, out_channels, kernel_size=kernel_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_down = self.pool(x)
        return self.conv(x_down)


class UpBlock1D(nn.Module):
    """Upscaling with ConvTranspose1D then DoubleConv1D with skip connection"""
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 11):
        super().__init__()
        self.up = nn.ConvTranspose1d(in_channels, in_channels // 2, kernel_size=4, stride=2, padding=1)
        self.conv = DoubleConv1D(in_channels, out_channels, kernel_size=kernel_size)

    def forward(self, x_deep: torch.Tensor, x_skip: torch.Tensor) -> torch.Tensor:
        x_up = self.up(x_deep)
        # Pad if odd sequence length
        diff = x_skip.size(-1) - x_up.size(-1)
        if diff > 0:
            x_up = F.pad(x_up, (0, diff))
        x_cat = torch.cat([x_skip, x_up], dim=1)
        return self.conv(x_cat)


class FECGUNet1D(nn.Module):
    """
    1D U-Net specifically sized for 1024-sample physiological time-series.
    Input shape:  [Batch, In_Channels, 1024]
    Output shape: [Batch, 1, 1024]
    """
    def __init__(self, in_channels: int = 1, base_filters: int = 32):
        super().__init__()
        self.in_conv = DoubleConv1D(in_channels, base_filters, kernel_size=15)
        self.down1 = DownBlock1D(base_filters, base_filters * 2, kernel_size=11)
        self.down2 = DownBlock1D(base_filters * 2, base_filters * 4, kernel_size=9)
        self.down3 = DownBlock1D(base_filters * 4, base_filters * 8, kernel_size=7)

        # Bottleneck at 1/16 resolution
        self.down4 = DownBlock1D(base_filters * 8, base_filters * 16, kernel_size=5)

        # Decoder stages
        self.up1 = UpBlock1D(base_filters * 16, base_filters * 8, kernel_size=7)
        self.up2 = UpBlock1D(base_filters * 8, base_filters * 4, kernel_size=9)
        self.up3 = UpBlock1D(base_filters * 4, base_filters * 2, kernel_size=11)
        self.up4 = UpBlock1D(base_filters * 2, base_filters, kernel_size=15)

        self.out_conv = nn.Conv1d(base_filters, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder
        x1 = self.in_conv(x)        # L
        x2 = self.down1(x1)         # L/2
        x3 = self.down2(x2)         # L/4
        x4 = self.down3(x3)         # L/8
        b  = self.down4(x4)         # L/16

        # Decoder with skip connections
        u1 = self.up1(b, x4)        # L/8
        u2 = self.up2(u1, x3)       # L/4
        u3 = self.up3(u2, x2)       # L/2
        u4 = self.up4(u3, x1)       # L

        out = self.out_conv(u4)
        return out


class CompositeECGLoss(nn.Module):
    """
    Combined Smooth L1 (Huber) + Numerically-Stable Negative Pearson Correlation Loss.
    Ensures waveform magnitude accuracy while strictly preserving QRS morphology and phase.
    """
    def __init__(self, alpha_l1: float = 1.0, beta_corr: float = 0.5):
        super().__init__()
        self.alpha_l1 = alpha_l1
        self.beta_corr = beta_corr
        self.smooth_l1 = nn.SmoothL1Loss(beta=0.01)

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        loss_l1 = self.smooth_l1(pred, target)

        # Pearson correlation per sequence in batch with strict numerical stability
        pred_mean = pred - pred.mean(dim=-1, keepdim=True)
        targ_mean = target - target.mean(dim=-1, keepdim=True)
        
        nom = torch.sum(pred_mean * targ_mean, dim=-1)
        eps = 1e-4
        pred_std = torch.sqrt(torch.sum(pred_mean ** 2, dim=-1) + eps)
        targ_std = torch.sqrt(torch.sum(targ_mean ** 2, dim=-1) + eps)
        
        corr = (nom / (pred_std * targ_std + eps)).clamp(min=-1.0, max=1.0)
        loss_corr = 1.0 - torch.mean(corr)

        return self.alpha_l1 * loss_l1 + self.beta_corr * loss_corr
