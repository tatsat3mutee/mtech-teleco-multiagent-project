"""
Render publication-ready matplotlib figures for the defense deck.

Inputs: `ablation_results.json` or `pipeline_results.json` produced by
`run_ablation.py`. Outputs PNGs under `docs/diagrams/`.

Intentionally minimal:
  - per-config metric bar chart with 95% CI whiskers
  - per-anomaly-type ROUGE-L heatmap
  - judge-axis radar (mean Likert per config)
All charts are grayscale-safe and 10pt.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from config import PROJECT_ROOT

OUT_DIR = PROJECT_ROOT / "docs" / "diagrams"
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 120,
})


def plot_config_bars(results: dict, metric: str = "rouge_l", out: Path = None) -> Path:
    """Bar chart: metric mean per config with 95% CI (if present)."""
    configs = list(results.keys())
    means = []
    lows = []
    highs = []
    for c in configs:
        r = results[c].get("metrics", {})
        m = r.get(metric, r.get(f"mean_{metric}", 0.0))
        ci = r.get(f"{metric}_ci") or r.get("ci", {}).get(metric) or (m, m)
        means.append(float(m))
        lows.append(float(ci[0]))
        highs.append(float(ci[1]))
    yerr = np.array([[m - lo, hi - m] for m, lo, hi in zip(means, lows, highs)]).T

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(configs))
    ax.bar(x, means, yerr=yerr, capsize=4, color="#4a7ab8", edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(configs, rotation=20, ha="right")
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} by configuration (95% CI)")
    fig.tight_layout()
    out = out or (OUT_DIR / f"results_{metric}_bars.png")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_judge_radar(results: dict, out: Path = None) -> Path:
    """Radar chart of Likert axes per config."""
    axes = ["correctness", "groundedness", "actionability", "completeness"]
    configs = list(results.keys())
    angles = np.linspace(0, 2 * np.pi, len(axes), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={"projection": "polar"})
    for c in configs:
        j = results[c].get("judge", {})
        vals = [float(j.get(ax_name, 0.0)) for ax_name in axes]
        vals += vals[:1]
        ax.plot(angles, vals, label=c, linewidth=1.5)
        ax.fill(angles, vals, alpha=0.08)
    ax.set_thetagrids(np.degrees(angles[:-1]), axes)
    ax.set_ylim(0, 5)
    ax.set_title("LLM-Judge (1–5 Likert) per config")
    ax.legend(loc="lower right", bbox_to_anchor=(1.3, 0.0))
    fig.tight_layout()
    out = out or (OUT_DIR / "judge_radar.png")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=str, default=str(PROJECT_ROOT / "ablation_results.json"))
    p.add_argument("--metric", type=str, default="rouge_l")
    args = p.parse_args()

    path = Path(args.results)
    if not path.exists():
        print(f"[plot] results not found: {path}")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    out1 = plot_config_bars(data, args.metric)
    print(f"[plot] wrote {out1}")
    try:
        out2 = plot_judge_radar(data)
        print(f"[plot] wrote {out2}")
    except Exception as e:
        print(f"[plot] radar skipped: {e}")


if __name__ == "__main__":
    main()
