import argparse
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from grading.configs import load_config
from grading.utils import identify_overlapping_judgments, load_judged_data


parser = argparse.ArgumentParser(description="Monitor the grading data.")
parser.add_argument("--config-base", default="configs/projects")
parser.add_argument("--save-file", default=None, help="Path to save the plot image.")
parser.add_argument("--regexes", nargs="*", default=None, help="Regexes to filter the files.")
parser.add_argument("--project")
args = parser.parse_args()


def _barplot(ax, data, *, title, xlabel, ylabel,):
    sns.barplot(x=list(data.keys()), y=list(data.values()), ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)

    ax.tick_params(axis="x", rotation=45, labelsize=10)
    for label in ax.get_xticklabels():
        label.set_ha("right")

    sns.despine(ax=ax, left=True, bottom=True)
    ax.set_facecolor("#f5f5f5")
    ax.grid(True, linewidth=0.3)

def main():

    project_cfg = load_config(os.path.join(args.config_base, f"{args.project}.yaml"))
    all_data = load_judged_data(project_cfg.judged_base_folder, regexes=args.regexes)

    unique_problems = {
        fname
        for folder in all_data.values()
        for fname in folder.keys()
    }

    def _count_if(predicate):
        return sum(
            1
            for folder in all_data.values()
            for fname in folder
            if predicate(folder[fname])
        )

    problems_with_issue = _count_if(lambda attempts: attempts[0]["problem_issue"])
    no_feedback_problems = _count_if(
        lambda attempts: any(a["no_feedback"] for a in attempts)
    )
    long_problems = _count_if(
        lambda attempts: any(a["long"] for a in attempts)
    )
    uncertain_problems = _count_if(lambda attempts: any(a["uncertain"] for a in attempts))

    avg_score = np.mean(
        [attempts[0]["score"] for folder in all_data.values() for attempts in folder.values()]
    )

    print("Overview of all data:")
    print(f"Number of unique problems: {len(unique_problems)}")
    print(
        f"Number of problems with issue: {problems_with_issue} "
        f"({problems_with_issue / len(unique_problems) * 100:.2f}%)"
    )
    print(
        f"Number of problems with no feedback: {no_feedback_problems} "
        f"({no_feedback_problems / len(unique_problems) * 100:.2f}%)"
    )
    print(
        f"Number of problems with long or tedious answer: {long_problems} "
        f"({long_problems / len(unique_problems) * 100:.2f}%)"
    )
    print(
        f"Number of problems with uncertain feedback: {uncertain_problems} "
        f"({uncertain_problems / len(unique_problems) * 100:.2f}%)"
    )
    print(f"Average score models: {avg_score:.2f}")

    # ───────────────────────────────────────────────── Overlap stats ─┐
    overlapping = identify_overlapping_judgments(all_data)
    if overlapping:
        eq_flags = [s["is_equal"] for s in overlapping]
        print(f"Overlap percentage ({len(eq_flags)} samples): {np.mean(eq_flags) * 100:.2f}%")
        certain_eq = [s for s in overlapping if not s["uncertain"]]
        if certain_eq:
            print(
                f"Overlap percentage without uncertain ({len(certain_eq)} samples): "
                f"{np.mean([s['is_equal'] for s in certain_eq]) * 100:.2f}%"
            )

    # ──────────────────────────────────────────────────────── Metrics ─┐
    avg_score_per_model = defaultdict(list)
    avg_overlap_per_judge = defaultdict(list)
    avg_given_score_per_judge = defaultdict(list)
    avg_score_per_competition = defaultdict(list)
    num_problems_per_judge = defaultdict(int)
    num_problems_per_competition = defaultdict(int)

    # aggregate
    for judge, judged_files in all_data.items():
        num_problems_per_judge[judge] = len(judged_files)
        for fname, attempts in judged_files.items():
            competition = fname.split("/")[0]
            if competition == "putnam" and attempts[0]["metadata"].get("url", "").startswith("https://raw.githubusercontent.com"):
                competition = "putnambench"
                
            num_problems_per_competition[competition] += 1

            for attempt in attempts:
                avg_score_per_model[attempt["model"]].append(attempt["score"])
                avg_given_score_per_judge[judge].append(attempt["score"])
                avg_score_per_competition[competition].append(attempt["score"])

    for sample in overlapping:
        if sample["uncertain"]:
            continue
        avg_overlap_per_judge[sample["judge"]].append(sample["is_equal"])
        avg_overlap_per_judge[sample["judge2"]].append(sample["is_equal"])

    # finalise means
    _mean = lambda d: {k: np.mean(v) for k, v in d.items()}
    avg_score_per_model = _mean(avg_score_per_model)
    avg_overlap_per_judge = _mean(avg_overlap_per_judge)
    avg_given_score_per_judge = _mean(avg_given_score_per_judge)
    avg_score_per_competition = _mean(avg_score_per_competition)

    # ─────────────────────────────────────────────────────────── Plots ─┐
    fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(12, 12))

    _barplot(
        axes[0, 0],
        avg_score_per_model,
        title="Average score per model",
        xlabel="Model",
        ylabel="Average score",
    )
    _barplot(
        axes[0, 1],
        avg_overlap_per_judge,
        title="Average overlap per judge",
        xlabel="Judge",
        ylabel="Average overlap",
    )
    _barplot(
        axes[0, 2],
        avg_given_score_per_judge,
        title="Average given score per judge",
        xlabel="Judge",
        ylabel="Average score",
    )
    _barplot(
        axes[1, 0],
        avg_score_per_competition,
        title="Average score per competition",
        xlabel="Competition",
        ylabel="Average score",
    )
    _barplot(
        axes[1, 1],
        num_problems_per_judge,
        title="Number of problems per judge",
        xlabel="Judge",
        ylabel="Number of problems",
    )
    _barplot(
        axes[1, 2],
        num_problems_per_competition,
        title="Number of problems per competition",
        xlabel="Competition",
        ylabel="Number of problems",
    )

    plt.tight_layout()
    
    if args.save_file:
        fig.savefig(args.save_file, bbox_inches="tight")
        print(f"Plot saved to {args.save_file}")
    else:
        plt.show()



if __name__ == "__main__":
    main()
