"""
Draw the eval progress chart from tests/eval_history.csv

  python tests/plot_eval.py
"""
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "eval_history.csv")
PNG_PATH = os.path.join(HERE, "eval_progress.png")
MIN_QUESTIONS = 30  # ignore small debugging runs


def load():
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                total = int(r["total"])
                passed = int(r["passed"])
                pct = float(r["percent"])
            except (TypeError, ValueError, KeyError):
                continue
            if total < MIN_QUESTIONS:
                continue
            rows.append({"time": r["time"], "label": r["label"], "passed": passed, "total": total, "pct": pct})
    return rows


def main():
    rows = load()
    if not rows:
        print("No full runs found in eval_history.csv")
        return

    print(f"{'time':<17} {'label':<28} {'score':>9}")
    for r in rows:
        print(f"{r['time']:<17} {r['label'][:28]:<28} {r['passed']:>3}/{r['total']:<3} {r['pct']:>5.1f}%")

    labels = [r["label"] for r in rows]
    values = [r["pct"] for r in rows]
    xs = list(range(len(rows)))

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(xs, values, marker="o", linewidth=2)
    for x, v in zip(xs, values):
        ax.annotate(f"{v:.1f}%", (x, v), textcoords="offset points", xytext=(0, 9), ha="center")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Questions answered correctly (%)")
    ax.set_title("Evaluation score by run")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=150)
    print(f"Saved {PNG_PATH}")


if __name__ == "__main__":
    main()