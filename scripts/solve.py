from grading.solve import solve, solve_agent
from grading.configs import load_config
from grading.best_of_n import single, random_selector, dual
from concurrent.futures import ThreadPoolExecutor
import os
import glob
import argparse
import re
from datetime import datetime
import json

def execute_judging_task(task_details):
    """
    Worker function to execute a single judging task.
    """
    project_config = task_details["project_config"]
    solver_config = task_details["solver_config"]
    files = task_details["files"]
    judge_part = task_details["judge_part"]

    mode = judge_part.get("mode")
    if mode in ["discrete", "continuous"]:
        single(project_config, solver_config, files, judge_part)
    elif mode == "random":
        random_selector(project_config, solver_config, files, judge_part)
    elif mode == "dual":
        dual(project_config, solver_config, files, judge_part)
    else:
        raise ValueError(f"Unknown judge mode: {mode}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Solve problems using the API.")
    parser.add_argument("--project")
    parser.add_argument("--config-base", default="configs/projects")
    parser.add_argument("--solve-config-path", default=None)

    args = parser.parse_args()

    project_config = load_config(os.path.join(args.config_base, args.project + ".yaml"))
    if args.solve_config_path:
        solver_config = load_config(args.solve_config_path)
    else:
        solver_config = load_config(project_config.solver_config)
    models_to_run = project_config.model_configs

    all_problem_files = glob.glob(f"{project_config.unsolved_base_folder}/**/*.json", recursive=True)

    files_to_run = [
        file for file in all_problem_files
        if any(re.match(regex, file.replace(project_config.unsolved_base_folder + "/", "")) for regex in solver_config.problem_regexes)
    ]

    if solver_config.earliest_date_added is not None:
        if " " not in solver_config.earliest_date_added:
            solver_config.earliest_date_added += " 00:00:00"
        date_threshold = datetime.strptime(solver_config.earliest_date_added, "%Y-%m-%d %H:%M:%S")
        files_to_actually_run = []
        for file in files_to_run:
            with open(file, "r") as f:
                data = json.load(f)
                if "date_added" in data and datetime.strptime(data["date_added"], "%Y-%m-%d %H:%M:%S") >= date_threshold:
                    files_to_actually_run.append(file)
    else:
        files_to_actually_run = files_to_run

    if solver_config.type == "proofagent":
        with ThreadPoolExecutor(max_workers=len(models_to_run)) as executor:
            futures = []
            for config_name in models_to_run:
                futures.append(
                    executor.submit(
                        solve_agent,
                        project_config,
                        solver_config,
                        files_to_actually_run,
                        config_name,
                    )
                )
            for future in futures:
                future.result()
    else:        


        print(f"Found {len(files_to_actually_run)} files to run.")
        with ThreadPoolExecutor(max_workers=len(models_to_run)) as executor:
            futures = []
            for config_name in models_to_run:
                futures.append(
                    executor.submit(
                        solve,
                        project_config,
                        solver_config,
                        files_to_actually_run,
                        config_name,
                    )
                )

            total_cost = 0
            for future in futures:
                total_cost += future.result()
        print(f"Total cost: {total_cost:.2f} USD")

    if solver_config.type == "best_of_n":
        files_to_judge = [
            file.replace(project_config.unsolved_base_folder, project_config.solved_base_folder)
            for file in files_to_actually_run
        ]

        # Prepare a list of all judging tasks to be executed
        judging_tasks = []
        for judge_part in solver_config.judges:
            for i, model in enumerate(models_to_run):
                if not judge_part.get("same_judge") and i > 0:
                    continue
                
                # Create a mutable copy of the judge configuration for each task
                current_judge_part = judge_part.copy()
                if current_judge_part.get("same_judge"):
                    current_judge_part["judge"] = model
                    current_judge_part["name"] = f"{model} {current_judge_part['name']}"

                task_details = {
                    "project_config": project_config,
                    "solver_config": solver_config,
                    "files": files_to_judge,
                    "judge_part": current_judge_part,
                }
                judging_tasks.append(task_details)

        # Execute the judging tasks in parallel using a ThreadPoolExecutor
        if judging_tasks:
            print(f"Running {len(judging_tasks)} judging tasks in parallel.")
            # Adjust max_workers as needed; here it's set to the number of tasks.
            with ThreadPoolExecutor(max_workers=len(judging_tasks)) as executor:
                futures = [executor.submit(execute_judging_task, task) for task in judging_tasks]
                # Wait for all judging tasks to complete
                for future in futures:
                    future.result()  # This will raise any exceptions that occurred in a thread

        for file in files_to_judge:
            data = json.load(open(file, "r"))
            if "attempts" not in data:
                continue
            # what we are going to do, is compress the attempts if the solution is the same
            attempts = data["attempts"]
            if len(attempts) == 0:
                continue
            compressed_attempts = []
            for attempt in attempts:
                to_add = True
                for i, existing_attempt in enumerate(compressed_attempts):
                    if existing_attempt["solution"] == attempt["solution"]:
                        to_add = False
                        if "other_selectors" not in existing_attempt:
                            existing_attempt["other_selectors"] = []
                        existing_attempt["other_selectors"].append(attempt)
        
                if to_add:
                    compressed_attempts.append(attempt)
            data["attempts"] = compressed_attempts
            with open(file, "w") as f:
                json.dump(data, f, indent=4)
