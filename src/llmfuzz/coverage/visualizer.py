"""Coverage comparison visualization using matplotlib."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_comparison(
    llm_progression: list[float],
    random_progression: list[float],
    target_name: str,
    output_path: str,
    llm_inputs: int = 0,
    random_inputs: int = 0,
) -> None:
    """Generate a coverage comparison chart: LLM-guided vs random."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot LLM-guided
    ax.plot(
        range(len(llm_progression)),
        llm_progression,
        "b-o",
        label=f"LLM-guided ({llm_inputs} inputs)",
        markersize=4,
        linewidth=2,
    )

    # Plot random
    ax.plot(
        range(len(random_progression)),
        random_progression,
        "r-s",
        label=f"Random ({random_inputs} inputs)",
        markersize=4,
        linewidth=2,
        alpha=0.7,
    )

    ax.set_xlabel("Iteration", fontsize=12)
    ax.set_ylabel("Branch Coverage (%)", fontsize=12)
    ax.set_title(f"Fuzzing Coverage: {target_name}", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 105)

    # Add final coverage annotation
    if llm_progression:
        ax.annotate(
            f"{llm_progression[-1]:.1f}%",
            xy=(len(llm_progression) - 1, llm_progression[-1]),
            xytext=(10, 5),
            textcoords="offset points",
            fontsize=10,
            color="blue",
            fontweight="bold",
        )
    if random_progression:
        ax.annotate(
            f"{random_progression[-1]:.1f}%",
            xy=(len(random_progression) - 1, random_progression[-1]),
            xytext=(10, -15),
            textcoords="offset points",
            fontsize=10,
            color="red",
            fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_coverage_over_time(
    progression: list[float],
    target_name: str,
    output_path: str,
) -> None:
    """Plot coverage progression for a single fuzzing session."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(
        range(len(progression)),
        progression,
        "b-o",
        markersize=4,
        linewidth=2,
    )

    ax.set_xlabel("Iteration", fontsize=12)
    ax.set_ylabel("Branch Coverage (%)", fontsize=12)
    ax.set_title(f"Coverage Growth: {target_name}", fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 105)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
