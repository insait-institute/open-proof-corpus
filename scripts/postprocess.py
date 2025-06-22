import argparse
from grading.configs import load_config
from grading.postprocess import process_sample, exclude_basic, join, exclude_discrepancy, train_test_split, random_train_test_split
import os
import json
import glob


def filter_matharena_putnam(all_samples):
    all_samples_new = []
    matharena = []
    putnam = []

    for sample in all_samples:
        if 'matharena' in sample['problem_id']:
            matharena.append(sample)
        elif 'PutnamBench' in sample['metadata']['url']:
            putnam.append(sample)
        else:
            all_samples_new.append(sample)

    return matharena, putnam, all_samples_new

def main():
    parser = argparse.ArgumentParser(description="Postprocess the grading results.")
    parser.add_argument("--project", type=str, required=True, help="Project name")
    parser.add_argument("--config-base", type=str, default="configs/projects")
    parser.add_argument("--exclude-regexes", type=str, nargs='*', default=[], help="Regexes of problem ids to exclude from postprocessing")
    parser.add_argument("--test-regexes", type=str, nargs='*', default=[], help="Regexes of problem ids to include in the test set")
    parser.add_argument("--save-folder", type=str, default="data/postprocess", help="Folder to save the postprocessed results")
    parser.add_argument("--random-sample", action='store_true')
    parser.add_argument("--hold-out-model", type=str, default='deepseek/r1_0528')

    args = parser.parse_args()
    
    project_config = load_config(os.path.join(args.config_base, f"{args.project}.yaml"))

    save_folder = os.path.join(args.save_folder, args.project)

    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    all_files = glob.glob(f"{project_config.judged_base_folder}/**/*.json", recursive=True)

    all_samples = []
    matharena = []
    putnam = []
    
    for file_name in all_files:
        judge_id = file_name.replace(project_config.judged_base_folder, "").split("/")[1]
        samples = process_sample(file_name, judge_id)
        all_samples.extend(samples)

    matharena, putnam, all_samples = filter_matharena_putnam(all_samples)
    
    print(f"Total samples before filtering: {len(all_samples)}")
    all_samples_filtered = exclude_basic(all_samples, args.exclude_regexes)
    print(f"Total samples after basic exclusion: {len(all_samples_filtered)}")
    all_samples_filtered = join(all_samples_filtered)
    print(f"Total samples after joining: {len(all_samples_filtered)}")
    all_samples_filtered = exclude_discrepancy(all_samples_filtered)
    print(f"Total samples after excluding discrepancies: {len(all_samples_filtered)}")
    if args.random_sample:
        train_samples, test_samples, hold_out_samples = random_train_test_split(all_samples_filtered, hold_out_model=args.hold_out_model)
    else:
        train_samples, test_samples = train_test_split(all_samples_filtered, args.test_regexes)
        hold_out_samples = []
    print(f"Total samples: {len(all_samples)}")
    print(f"Total clean samples: {len(all_samples_filtered)}")
    print(f"Train samples: {len(train_samples)}")
    print(f"Test samples: {len(test_samples)}")
    print(f"MathArena samples: {len(matharena)}")
    print(f"PutnamBench samples: {len(putnam)}")
    print(f"Hold-out model samples: {len(hold_out_samples)}")



    # save as jsonl files
    with open(os.path.join(save_folder, "train_samples.json"), "w") as f:
        json.dump(train_samples, f, indent=4)
    with open(os.path.join(save_folder, "filtered_samples.json"), "w") as f:
        json.dump(all_samples_filtered, f, indent=4)
    with open(os.path.join(save_folder, "test_samples.json"), "w") as f:
        json.dump(test_samples, f, indent=4)
    with open(os.path.join(save_folder, "all_samples.json"), "w") as f:
        json.dump(all_samples, f, indent=4)
    if len(matharena) > 0:
        with open(os.path.join(save_folder, "matharena.json"), "w") as f:
            json.dump(matharena, f, indent=4)
    if len(putnam) > 0:
        with open(os.path.join(save_folder, "putnambench.json"), "w") as f:
            json.dump(putnam, f, indent=4)
    if len(putnam) > 0:
        with open(os.path.join(save_folder, "holdout.json"), "w") as f:
            json.dump(hold_out_samples, f, indent=4)
    
if __name__ == "__main__":
    main()


