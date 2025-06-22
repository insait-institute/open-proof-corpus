import argparse
import os
import yaml
import json
import pandas as pd
from tqdm import tqdm
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--project", type=str, required=True)

if __name__ == '__main__':
    args = parser.parse_args()
    output_dir = os.path.join('./data', args.project)
    results = []
        
    with open(os.path.join(output_dir, 'all_samples.json'), 'r') as f:
        data = json.load(f)

    for sample in data:
        comp = sample['metadata']['source']
        solution = sample['solution']
        gt = 0 if any([grading['score']==0 for grading in sample['grading']]) else 1
        model = sample['model_id']
        cost = sample['cost']['cost']
        results.append({
            'comp': comp,
            'solution': solution,
            'grade': gt,
            'model': model,
            'cost': cost
        })
        if 'other_selectors' in sample:
            for selector in sample['other_selectors']:
                model = selector['model_id']
                cost = selector['cost']['cost']
                results.append({
                    'comp': comp,
                    'solution': solution,
                    'grade': gt,
                    'model': model,
                    'cost': cost
                })

    df = pd.DataFrame(results)

    print("\n=== Overall Judge Statistics ===")
    judge_stats = df.groupby('model').agg(
        avg_accuracy=('grade', 'mean'),
        num_problems=('grade', 'count'),
        cost=('cost', 'sum')
    ).reset_index()
    print(judge_stats.to_string(index=False))

    print("\n=== Judge Accuracy per Competition ===")
    comp_stats = df.groupby(['model', 'comp']).agg(
        avg_accuracy=('grade', 'mean'),
        num_problems=('grade', 'count')
    ).reset_index()
    print(comp_stats.to_string(index=False))