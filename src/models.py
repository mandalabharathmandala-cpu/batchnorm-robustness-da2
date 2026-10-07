"""
Custom Normalization Layers and Convolution with Weight Standardization (WS-Conv2d).

Addresses Paper #3 Loophole:
- Batch Normalization breaks when mini-batch size B <= 4 due to inaccurate batch statistics (\mu_B, \sigma_B^2).
- Weight Standardization (WS) standardizes convolutional weights along (Cin * K * K), making gradients Lipschitz-continuous.
- Combined with Group Normalization (WS-GN), this provides completely batch-size invariant optimization.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

class WeightStandardizedConv2d(nn.Conv2d):
    """
    Conv2d layer with Weight Standardization (WS).
    Weights W are normalized along fan-in (Cin * K * K):
        W_hat = (W - mean(W)) / (std(W) + eps)
    Eliminates scale/shift drift in gradients independent of batch size.
    """
    def __init__(self, in_channels, out_channels, kernel_size, stride=1,
                 padding=0, dilation=1, groups=1, bias=True, eps=1e-5):
        super(WeightStandardizedConv2d, self).__init__(
            in_channels, out_channels, kernel_size, stride,
            padding, dilation, groups, bias
        )
        self.eps = eps

    def forward(self, x):
        weight = self.weight
        weight_mean = weight.mean(dim=(1, 2, 3), keepdim=True)
        weight_std = weight.std(dim=(1, 2, 3), keepdim=True) + self.eps
        normalized_weight = (weight - weight_mean) / weight_std
        return F.conv2d(
            x, normalized_weight, self.bias, self.stride,
            self.padding, self.dilation, self.groups
        )


class ConvBlock(nn.Module):
    """
    Modular Convolutional block supporting:
    - 'bn': Standard Batch Normalization (Ioffe & Szegedy, 2015)
    - 'gn': Group Normalization (Wu & He, 2018)
    - 'ln': Layer Normalization (Ba et al., 2016)
    - 'in': Instance Normalization (Ulyanov et al., 2016)
    - 'ws_gn': Proposed: Weight Standardization + Group Normalization
    """
    def __init__(self, in_channels, out_channels, norm_type='bn', num_groups=8):
        super(ConvBlock, self).__init__()
        self.norm_type = norm_type

        if norm_type == 'ws_gn':
            self.conv = WeightStandardizedConv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
            self.norm = nn.GroupNorm(num_groups=min(num_groups, out_channels), num_channels=out_channels)
        elif norm_type == 'bn':
            self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
            self.norm = nn.BatchNorm2d(out_channels)
        elif norm_type == 'gn':
            self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
            self.norm = nn.GroupNorm(num_groups=min(num_groups, out_channels), num_channels=out_channels)
        elif norm_type == 'ln':
            self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
            self.norm = nn.GroupNorm(num_groups=1, num_channels=out_channels)
        elif norm_type == 'in':
            self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
            self.norm = nn.InstanceNorm2d(out_channels, affine=True)
        elif norm_type == 'none':
            self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=True)
            self.norm = nn.Identity()
        else:
            raise ValueError(f"Unsupported norm_type: {norm_type}")

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        return self.relu(self.norm(self.conv(x)))


class SmallResNet(nn.Module):
    """
    Residual Network with customizable normalization for small-batch robustness evaluation.
    """
    def __init__(self, num_classes=10, in_channels=1, norm_type='bn', num_groups=8):
        super(SmallResNet, self).__init__()
        self.norm_type = norm_type

        self.layer1 = ConvBlock(in_channels, 32, norm_type=norm_type, num_groups=num_groups)
        self.layer2 = ConvBlock(32, 64, norm_type=norm_type, num_groups=num_groups)
        self.pool1 = nn.MaxPool2d(2, 2)

        self.layer3 = ConvBlock(64, 64, norm_type=norm_type, num_groups=num_groups)
        self.layer4 = ConvBlock(64, 128, norm_type=norm_type, num_groups=num_groups)
        self.pool2 = nn.MaxPool2d(2, 2)

        self.layer5 = ConvBlock(128, 128, norm_type=norm_type, num_groups=num_groups)
        self.pool3 = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.layer1(x)
        x = self.pool1(self.layer2(x))
        x = self.layer3(x)
        x = self.pool2(self.layer4(x))
        x = self.pool3(self.layer5(x))
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x
