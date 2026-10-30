"""Dark HUD-style plots for the anomaly model report."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np


def plot_confusion_matrix(
    matrix: Sequence[Sequence[int]],
    path: str | Path,
    *,
    threshold: float,
    f1: float,
) -> None:
    """Render a compact dark confusion matrix PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    values = np.asarray(matrix, dtype=float)
    total = max(1.0, values.sum())
    cmap = LinearSegmentedColormap.from_list(
        "chaospilot", ["#071119", "#123844", "#20b9b4", "#20e7de"]
    )

    figure, axes = plt.subplots(figsize=(5.6, 4.6), facecolor="#050810")
    axes.set_facecolor("#050810")
    image = axes.imshow(values, cmap=cmap, vmin=0, vmax=max(1.0, values.max()))

    labels = ("normal", "fault")
    for row in range(2):
        for column in range(2):
            count = int(values[row][column])
            share = count / total
            bright = values[row][column] > values.max() * 0.55
            axes.text(
                column,
                row - 0.08,
                str(count),
                ha="center",
                va="center",
                fontsize=22,
                fontweight="bold",
                color="#04121a" if bright else "#9fe8ef",
            )
            axes.text(
                column,
                row + 0.20,
                f"{share:.1%}",
                ha="center",
                va="center",
                fontsize=9,
                color="#04121a" if bright else "#5f8c93",
            )

    axes.set_xticks([0, 1], labels)
    axes.set_yticks([0, 1], labels)
    axes.set_xlabel("predicted", color="#9fe8ef", labelpad=8)
    axes.set_ylabel("actual", color="#9fe8ef", labelpad=8)
    axes.set_title(
        f"Anomaly detector · threshold {threshold:.2f} · F1 {f1:.2f}",
        color="#e7feff",
        fontsize=11,
        pad=14,
    )
    axes.tick_params(colors="#9fe8ef")
    for spine in axes.spines.values():
        spine.set_color("#20e7de")
        spine.set_alpha(0.35)
    colorbar = figure.colorbar(image, ax=axes, fraction=0.046, pad=0.04)
    colorbar.ax.tick_params(colors="#5f8c93", labelsize=8)
    colorbar.outline.set_edgecolor("#20e7de")
    colorbar.outline.set_alpha(0.3)

    figure.tight_layout()
    figure.savefig(destination, dpi=150, facecolor=figure.get_facecolor())
    plt.close(figure)
