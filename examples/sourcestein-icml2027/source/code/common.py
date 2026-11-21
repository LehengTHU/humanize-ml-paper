"""Shared data loading and model definitions (CIFAR-10 / CIFAR-10-C, two BN backbones)."""
import os, pickle, numpy as np, torch, torch.nn as nn, torch.nn.functional as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
MEAN = np.array([0.4914, 0.4822, 0.4465], dtype=np.float32)
STD = np.array([0.2470, 0.2435, 0.2616], dtype=np.float32)
CORRUPTIONS = ["gaussian_noise", "shot_noise", "impulse_noise", "defocus_blur", "glass_blur", "motion_blur",
               "zoom_blur", "snow", "frost", "fog", "brightness", "contrast", "elastic_transform", "pixelate",
               "jpeg_compression"]


def to_tensor(u8):  # (N,32,32,3) uint8 -> normalised (N,3,32,32) float tensor
    x = (u8.astype(np.float32) / 255.0 - MEAN) / STD
    return torch.from_numpy(x.transpose(0, 3, 1, 2).copy())


def load_cifar10(split):
    d = os.path.join(DATA, "cifar-10-batches-py")
    files = [f"data_batch_{i}" for i in range(1, 6)] if split == "train" else ["test_batch"]
    xs, ys = [], []
    for f in files:
        b = pickle.load(open(os.path.join(d, f), "rb"), encoding="bytes")
        xs.append(b[b"data"].reshape(-1, 3, 32, 32).transpose(0, 2, 3, 1)); ys += b[b"labels"]
    return np.concatenate(xs), np.array(ys)


def load_c10c(corruption, severity):
    x = np.fromfile(os.path.join(DATA, "c10c", f"{corruption}_s{severity}.u8"), dtype=np.uint8).reshape(-1, 32, 32, 3)
    y = np.fromfile(os.path.join(DATA, "c10c", "labels.u8"), dtype=np.uint8).astype(np.int64)
    return x, y


class VGG(nn.Module):  # "CNN-8": 6 conv + BN layers, global pooling, linear head
    def __init__(self, w=(32, 64, 128), n_cls=10):
        super().__init__()
        layers, c_in = [], 3
        for c in w:
            for _ in range(2):
                layers += [nn.Conv2d(c_in, c, 3, padding=1, bias=False), nn.BatchNorm2d(c), nn.ReLU(inplace=True)]
                c_in = c
            layers.append(nn.MaxPool2d(2))
        self.features = nn.Sequential(*layers)
        self.fc = nn.Linear(c_in, n_cls)

    def forward(self, x):
        return self.fc(F.adaptive_avg_pool2d(self.features(x), 1).flatten(1))


class Block(nn.Module):
    def __init__(self, c_in, c, stride):
        super().__init__()
        self.c1 = nn.Conv2d(c_in, c, 3, stride, 1, bias=False); self.b1 = nn.BatchNorm2d(c)
        self.c2 = nn.Conv2d(c, c, 3, 1, 1, bias=False); self.b2 = nn.BatchNorm2d(c)
        self.sc = None
        if stride != 1 or c_in != c:
            self.sc = nn.Sequential(nn.Conv2d(c_in, c, 1, stride, bias=False), nn.BatchNorm2d(c))

    def forward(self, x):
        o = F.relu(self.b1(self.c1(x)))
        o = self.b2(self.c2(o))
        return F.relu(o + (x if self.sc is None else self.sc(x)))


class ResNet(nn.Module):  # CIFAR ResNet-(6n+2) (He et al., 2016): 3 stages x n blocks, widths 16/32/64
    def __init__(self, n=2, n_cls=10):
        super().__init__()
        self.c = nn.Conv2d(3, 16, 3, 1, 1, bias=False); self.b = nn.BatchNorm2d(16)
        blocks, c_in = [], 16
        for i, c in enumerate((16, 32, 64)):
            for j in range(n):
                blocks.append(Block(c_in, c, 2 if (j == 0 and i > 0) else 1)); c_in = c
        self.blocks = nn.Sequential(*blocks)
        self.fc = nn.Linear(64, n_cls)

    def forward(self, x):
        x = self.blocks(F.relu(self.b(self.c(x))))
        return self.fc(F.adaptive_avg_pool2d(x, 1).flatten(1))


def make_model(name):
    return {"cnn8": VGG, "resnet14": ResNet}[name]()
