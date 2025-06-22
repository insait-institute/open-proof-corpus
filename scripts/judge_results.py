import argparse
import os
import yaml
import json
import numpy as np
import pandas as pd
from tqdm import tqdm
from pathlib import Path
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import rcParams

parser = argparse.ArgumentParser()
parser.add_argument("--setting_config", type=str, required=True)
parser.add_argument("--output-folder", type=str, default="outputs")
parser.add_argument("--configs-folder", type=str, default="configs/")

def process_problem(problem_path, judge_config, solver_config, solver_name = None):
    with open(problem_path, 'r') as f:
        problem_data = json.load(f)
    if 'discrete' in str(problem_path) and os.path.exists(str(problem_path).replace('discrete', 'continuous')):
        with open(str(problem_path).replace('discrete', 'continuous'), 'r') as f:
            cont_data = json.load(f)
    else:
        cont_data=None
    return {
        "judge": judge_config['human_readable_id'],
        "solver": solver_config['human_readable_id'] if solver_name is None else solver_name,
        "problem": problem_data['problem_id'],
        "competition": problem_data['metadata']['source'],
        "true_grade": problem_data['gold_judgement'],
        "accuracy": problem_data['pass_at_1'],
        "maj_accuracy": float(problem_data['maj_at_n']),
        "cont_score": np.nan if cont_data is None else cont_data['pass_at_1'],
        "cost": problem_data['cost']['cost'],
    }

if __name__ == '__main__':
    args = parser.parse_args()
    output_dir = os.path.join(args.output_folder, args.setting_config.replace('.yaml', ''))
    results = []
        
    output_path = Path(output_dir)
    config_path = Path(args.configs_folder)

    for problem_path in tqdm(output_path.glob('*/*/*/*/*')):
        judge_api, judge_model, solver_api, solver_model, _ = problem_path.parts[-5:]

        if os.path.exists(config_path / "models" / judge_api / f'{judge_model}.yaml'):
            with open(config_path / "models" / judge_api / f'{judge_model}.yaml', 'r') as f:
                judge_config = yaml.safe_load(f)

        if ' ' in solver_model and os.path.exists(config_path / "models" / solver_api / f'{solver_model.split(' ')[0]}.yaml'):
            with open(config_path / "models" / solver_api / f'{solver_model.split(' ')[0]}.yaml', 'r') as f:
                solver_config = yaml.safe_load(f)
            results.append(process_problem(str(problem_path), judge_config, solver_config, solver_name=solver_model))

        elif os.path.exists(config_path / "models" / solver_api / f'{solver_model}.yaml'):
            with open(config_path / "models" / solver_api / f'{solver_model}.yaml', 'r') as f:
                solver_config = yaml.safe_load(f)

            results.append(process_problem(str(problem_path), judge_config, solver_config))

    df = pd.DataFrame(results)

    print("\n=== Overall Judge Statistics ===")
    judge_stats = df.groupby('judge').agg(
        avg_accuracy=('accuracy', 'mean'),
        maj_voting_accuracy=('maj_accuracy', 'mean'),
        cont_score=('cont_score', 'mean'),
        num_problems=('accuracy', 'count'),
        cost=('cost', 'sum')
    ).reset_index()
    print(judge_stats.to_string(index=False))

    print("\n=== Solver Accuracy per Judge (with Ground Truth) ===")
    solver_stats = df.groupby(['judge', 'solver']).agg(
        avg_accuracy=('accuracy', 'mean'),
        cont_score=('cont_score', 'mean')
    ).reset_index()

    gt_stats = df.groupby('solver').agg(
        ground_truth_accuracy=('maj_accuracy', 'mean')
    ).reset_index()

    merged = solver_stats.merge(gt_stats, on='solver')
    print(merged.to_string(index=False))

    print("\n=== Judge Accuracy per Competition ===")
    comp_stats = df.groupby(['judge', 'competition']).agg(
        avg_accuracy=('accuracy', 'mean'),
        cont_score=('cont_score', 'mean'),
        maj_voting_accuracy=('maj_accuracy', 'mean'),
        num_problems=('accuracy', 'count')
    ).reset_index()
    print(comp_stats.to_string(index=False))

    model_map = {
        "Claude-4-Sonnet (Think)": '\\textsc{Claude 4 Sonnet}',
        "DeepSeek-R1 (05/28)": '\\textsc{DeepSeek R1 (05/28)}',
        "DeepSeek-R1-05-28": '\\textsc{DeepSeek R1 (05/28)}',
        "DeepSeek-R1-Distill-14B": '\\textsc{DeepSeek R1 14B}',
        "DeepSeek-R1-Qwen3-8B": '\\textsc{DeepSeek R1 8B (05/28)}',
        "DeepSeek-R1-Qwen3-8B+OPC": '\\textsc{OPC R1 8B}',
        "discrete_long": '\\textsc{OPC R1 8B (long)}',
        "Naive Baseline": '\\textsc{Baseline}',
        "Qwen3-235B-A22B": '\\textsc{Qwen3 235B-A22B}',
        "Qwen3-32B": '\\textsc{Qwen3 32B}',
        "Qwen3-8B": '\\textsc{Qwen3 8B}',
        'gemini-2.5-flash (think)': '\\textsc{Gemini-Flash}',
        "gemini-2.5-pro": '\\textsc{Gemini-Pro}',
        'gpt-4.1': '\\textsc{GPT 4.1}',
        'o3 (high)': '\\textsc{o3}',
        'o4-mini (high)': '\\textsc{o4-mini}'
    }

    latex_df = judge_stats[["judge", "avg_accuracy", "maj_voting_accuracy", "cost"]].copy()
    latex_df.columns = ["Judge", "pass@1", "maj@5", "Cost"]

    # Format float values
    latex_df['Judge'] = latex_df['Judge'].apply(lambda x: model_map[x])
    latex_df["pass@1"] = (latex_df["pass@1"]*100).map("{:.1f}".format)
    latex_df["maj@5"] = (latex_df["maj@5"]*100).map("{:.1f}".format)
    latex_df["Cost"] = latex_df["Cost"].map("{:,.2f}".format)
    latex_df = latex_df.sort_values(by='pass@1', ascending=False)
    # Generate LaTeX
    latex_table = latex_df.to_latex(index=False, escape=False, column_format='lccc', caption="Judge Performance Summary", label="tab:judge_summary")

    print(latex_table)
