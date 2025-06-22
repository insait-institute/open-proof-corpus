from grading.solve import solve
from grading.configs import load_config
from grading.best_of_n import single, random_selector, dual
from concurrent.futures import ThreadPoolExecutor
import os
import glob
import argparse
import re
from datetime import datetime
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Solve problems using the API.")
    parser.add_argument("--project")
    parser.add_argument("--config-base", default="configs/projects")
    parser.add_argument("--store-file")
    parser.add_argument("--temp-folder", default="temp")

    args = parser.parse_args()

    project_config = load_config(os.path.join(args.config_base, args.project + ".yaml"))

    solver_config = load_config(project_config.solver_config)

    files = glob.glob(f"data/judged/pass_at_n/**/*.json", recursive=True)

    if os.path.exists(args.store_file):
        existing_files = json.load(open(args.store_file, "r"))
        existing_problem_ids = {file["problem_id"] for file in existing_files}
    else:
        existing_problem_ids = set()

    # copy all files to the temp folder
    if not os.path.exists(args.temp_folder):
        os.makedirs(args.temp_folder)
    files_to_run = []
    for file in files:

        filename = file.replace(project_config.judged_base_folder + "/", "")
        
        os.makedirs(os.path.dirname(os.path.join(args.temp_folder, filename)), exist_ok=True)
        data = json.load(open(file, "r"))
        if data["problem_id"] in existing_problem_ids:
            continue

        files_to_run.append(os.path.join(args.temp_folder, filename))

        if os.path.exists(os.path.join(args.temp_folder, filename)):
            continue
        data["attempts_singular"] = data["attempts"]
        del data["attempts"]
        with open(os.path.join(args.temp_folder, filename), "w") as f:
            json.dump(data, f, indent=4)
    
    for judge_part in solver_config.judges:
        if judge_part["mode"] in ["discrete", "continuous"]:
            single(project_config, solver_config, files_to_run, judge_part)
        elif judge_part["mode"] == "random":
            random_selector(project_config, solver_config, files_to_run, judge_part)
        elif judge_part["mode"] == "dual":
            judge_part["tournament_config"]["round_robin"] = True # set this to work better
            dual(project_config, solver_config, files_to_run, judge_part)
        else:
            raise ValueError(f"Unknown judge mode: {judge_part['mode']}")

    actual_data = []
    for file in files:
        filename = file.replace(project_config.judged_base_folder + "/", "")
        try:
            data = json.load(open(os.path.join(args.temp_folder, filename), "r"))
        except:
            pass # problem was double judged
        correctness = [
            attempt["grading"].get("score", 0) for attempt in data["attempts_singular"]
        ]
        judge_data = {
            attempt["model_id"]: attempt.get("judge_data", None) for attempt in data["attempts"]
        }
        actual_data.append({
            "problem_id": data["problem_id"],
            "correctness": correctness,
            "judge_data": judge_data,
        })

    with open(args.store_file, "w") as f:
        json.dump(actual_data, f, indent=4)

    
