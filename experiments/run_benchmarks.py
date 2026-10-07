"""
Benchmarking experiment runner across normalization strategies and mini-batch sizes.
Optimized for clean, fast CPU execution with representative sample budgets.
"""

import time
import json
import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from src.models import SmallResNet
from src.datasets import get_dataloaders

def train_and_evaluate(norm_type, batch_size, epochs=2, lr=0.002, dataset="fashion_mnist", device="cpu"):
    print(f"\n=======================================================")
    print(f"Running Experiment: Norm={norm_type.upper():<6} | Batch Size={batch_size}")
    print(f"=======================================================")

    train_loader, test_loader, in_channels = get_dataloaders(
        dataset_name=dataset,
        batch_size=batch_size,
        num_train_samples=2500,
        num_test_samples=800
    )

    model = SmallResNet(num_classes=10, in_channels=in_channels, norm_type=norm_type).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)

    history = {
        "norm_type": norm_type,
        "batch_size": batch_size,
        "train_loss": [],
        "val_acc": [],
        "grad_norms": [],
        "epoch_times": []
    }

    start_total_time = time.time()

    for epoch in range(epochs):
        epoch_start = time.time()
        model.train()
        running_loss = 0.0
        grad_norms_epoch = []
        batch_count = 0

        for batch_idx, (images, labels) in enumerate(train_loader):
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()

            # Record gradient norm of first conv layer for stability analysis
            if hasattr(model.layer1.conv, 'weight') and model.layer1.conv.weight.grad is not None:
                g_norm = model.layer1.conv.weight.grad.norm().item()
                grad_norms_epoch.append(g_norm)

            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()

            running_loss += loss.item()
            batch_count += 1

        epoch_time = time.time() - epoch_start
        avg_loss = running_loss / max(1, batch_count)
        avg_grad_norm = float(np.mean(grad_norms_epoch)) if grad_norms_epoch else 0.0
        grad_variance = float(np.var(grad_norms_epoch)) if grad_norms_epoch else 0.0

        # Evaluation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for images, labels in test_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        val_accuracy = 100.0 * correct / total
        history["train_loss"].append(round(avg_loss, 4))
        history["val_acc"].append(round(val_accuracy, 2))
        history["grad_norms"].append(round(avg_grad_norm, 4))
        history["epoch_times"].append(round(epoch_time, 2))

        print(f"Epoch [{epoch+1}/{epochs}] Loss: {avg_loss:.4f} | Val Acc: {val_accuracy:.2f}% | Grad Norm: {avg_grad_norm:.4f} (Var: {grad_variance:.4f}) | Time: {epoch_time:.2f}s")

    total_training_time = time.time() - start_total_time

    # Inference latency benchmark
    model.eval()
    sample_batch = torch.randn(100, in_channels, 28, 28).to(device)
    for _ in range(3):
        _ = model(sample_batch)
    lat_start = time.time()
    for _ in range(10):
        _ = model(sample_batch)
    inf_latency_ms = (time.time() - lat_start) * 1000 / 10
    inf_latency_1k = round(inf_latency_ms * 10, 2)

    final_metrics = {
        "norm_type": norm_type,
        "batch_size": batch_size,
        "final_val_acc": history["val_acc"][-1],
        "final_loss": history["train_loss"][-1],
        "avg_grad_norm": round(float(np.mean(history["grad_norms"])), 4),
        "grad_variance": round(float(np.var(history["grad_norms"])), 4),
        "total_training_time_sec": round(total_training_time, 2),
        "inf_latency_ms_per_1k": inf_latency_1k,
        "parameter_count": param_count,
        "history": history
    }

    return final_metrics

def run_suite():
    os.makedirs("results", exist_ok=True)
    device = "cpu"
    print(f"Running benchmarks on device: {device}")

    # Mini-batch sizes to test: 64 (large), 16 (moderate), 4 (small), 2 (extreme small)
    batch_sizes = [64, 16, 4, 2]
    norm_types = ["bn", "ws_gn", "gn", "ln"]

    all_results = []

    for bs in batch_sizes:
        for norm in norm_types:
            res = train_and_evaluate(norm_type=norm, batch_size=bs, epochs=2, device=device)
            all_results.append(res)
            with open("results/benchmark_results.json", "w") as f:
                json.dump(all_results, f, indent=2)

    print("\nBenchmark Suite Completed successfully! Results written to results/benchmark_results.json")

if __name__ == "__main__":
    run_suite()
