"""
Draws the score history from tests/eval_history.csv into tests/eval_progress.png.
  pip install matplotlib
  python tests/plot_eval.py
Without matplotlib it prints a text table instead.
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "eval_history.csv")
OUT = os.path.join(HERE, "eval_progress.png")


def main():
    if not os.path.exists(SRC):
        print("No history yet. Run: python tests/eval_chat.py --label baseline")
        return
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    print(f"{'#':>2}  {'time':<16} {'score':>6}  label")
    for i, r in enumerate(rows, 1):
        print(f"{i:>2}  {r['time']:<16} {r['percent']:>5}%  {r['label']}")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n(install matplotlib to also get a chart: pip install matplotlib)")
        return

    xs = list(range(1, len(rows) + 1))
    ys = [float(r["percent"]) for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(xs, ys, marker="o", linewidth=2, color="#1f77b4")
    for x, y, r in zip(xs, ys, rows):
        ax.annotate(f"{y:g}%", (x, y), textcoords="offset points", xytext=(0, 8), ha="center")
    ax.set_xticks(xs)
    ax.set_xticklabels([r["label"] for r in rows], rotation=25, ha="right")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Questions passed (%)")
    ax.set_title("Shop assistant evaluation score over time")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print(f"\nChart saved to {OUT}")


if __name__ == "__main__":
    main()