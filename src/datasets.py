"""
Dataset pipeline with deterministic subsampling and variable batch loaders
Supports Fashion-MNIST and CIFAR-10.
"""

import torch
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, Subset

def get_dataloaders(dataset_name="fashion_mnist", batch_size=32, data_dir="./data/raw", num_train_samples=5000, num_test_samples=1000):
    if dataset_name == "fashion_mnist":
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.2860,), (0.3530,))
        ])
        train_ds = datasets.FashionMNIST(root=data_dir, train=True, download=True, transform=transform)
        test_ds = datasets.FashionMNIST(root=data_dir, train=False, download=True, transform=transform)
        in_channels = 1
    elif dataset_name == "cifar10":
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616))
        ])
        train_ds = datasets.CIFAR10(root=data_dir, train=True, download=True, transform=transform)
        test_ds = datasets.CIFAR10(root=data_dir, train=False, download=True, transform=transform)
        in_channels = 3
    else:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    if num_train_samples and num_train_samples < len(train_ds):
        train_ds = Subset(train_ds, list(range(num_train_samples)))
    if num_test_samples and num_test_samples < len(test_ds):
        test_ds = Subset(test_ds, list(range(num_test_samples)))

    # Drop last batch to avoid batch size of 1 when running tiny batches
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=(batch_size <= 4))
    test_loader = DataLoader(test_ds, batch_size=64, shuffle=False)

    return train_loader, test_loader, in_channels
