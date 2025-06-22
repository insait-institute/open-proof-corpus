import os
import glob
import json
import random
import math
import re
from loguru import logger
from .recover import fully_resolved, recover
from .configs import load_config
from .utils import load_judged_data, identify_overlapping_judgments

def satisfies_constraints(data, judge, file):
    if data["metadata"].get("level", "highschool") == "undergraduate" and not judge["undergraduate"]:
        return False
    if data["metadata"].get("level", "highschool") != "undergraduate" and judge.get("only_undergraduate", False):
        return False
    if "problems" in judge:
        for problem in judge["problems"]:
            if re.match(problem, file):
                return True
        return False
    return True

def fully_resolved_no_skip(data):
    if data.get("useless"):
        return True
    for attempt in data["attempts"]:
        if attempt["grading"] is None:
            return False
        if attempt["grading"].get("long"):
            continue
        if attempt["grading"]["no_feedback"]:
            return False
        if attempt["grading"]["score"] is None:
            return False
        if any(rubric["score"] is None for rubric in attempt["grading"]["details"]):
            return False
        if any(rubric["feedback"] is None for rubric in attempt["grading"]["details"]):
            return False
    return True

def any_skipped(data):
    for attempt in data["attempts"]:
        if attempt["grading"] is None:
            continue
        if attempt["grading"]["no_feedback"]:
            return True
    return False

def fully_not_resolved(data):
    for attempt in data["attempts"]:
        if attempt["grading"] is None:
            continue
        if attempt["grading"]["no_feedback"]:
            return False
        if attempt["grading"]["score"] is not None:
            return False
        if any(rubric["score"] is not None for rubric in attempt["grading"]["details"]):
            return False
        if any(rubric["feedback"] is not None for rubric in attempt["grading"]["details"]):
            return False
    return True

def find_existing_files(project_config, all_judge_ids):
    all_judged_files = glob.glob(f"{project_config.judged_base_folder}/**/*.json", recursive=True)
    all_website_files = glob.glob(f"{project_config.website_folder}/**/*.json", recursive=True)
    existing_files = []

    for file in all_judged_files:
        data = json.load(open(file, "r"))
        if os.path.exists(file.replace(project_config.judged_base_folder, project_config.website_folder)):
            continue

        judge_id = file.replace(project_config.judged_base_folder + "/", "").split("/")[0]
        if judge_id not in all_judge_ids:
            continue
        existing_files.append({
            "problem": file.replace(project_config.judged_base_folder + "/" + judge_id + "/", ""),
            "website": False,
            "judge": judge_id,
            "resolved": True,
            "resolved_no_skip": fully_resolved_no_skip(data),
            "skipped": any_skipped(data),
        })
    
    for file in all_website_files:
        if any("/" + skip + "/" in file for skip in [project_config.discrepancies_slug, project_config.problems_slug, project_config.solutions_slug]):
            continue
        data = json.load(open(file, "r"))
        judge_id = file.replace(project_config.website_folder + "/", "").split("/")[0]
        if judge_id not in all_judge_ids:
            continue
        existing_files.append({
            "problem": file.replace(project_config.website_folder + "/" + judge_id + "/", ""),
            "website": True,
            "judge": judge_id,
            "resolved": fully_resolved(data),
            "resolved_no_skip": fully_resolved_no_skip(data),
            "skipped": any_skipped(data),
        })
    return existing_files

def get_all_problems(project_config):
    all_problem_files = glob.glob(f"{project_config.solved_base_folder}/**/*.json", recursive=True)
    all_problems = []
    for file in all_problem_files:
        data_problem_solved = json.load(open(file, "r"))
        if "attempts" not in data_problem_solved or len(data_problem_solved["attempts"]) == 0:
            continue
        all_problems.append(file.replace(project_config.solved_base_folder + "/", ""))
    
    all_problems.sort()
    return all_problems

def filter_all_problems(all_problems, existing_file_data):
    filtered_problems = dict()
    for problem in all_problems:
        existing_of_problem = [data for data in existing_file_data if data["problem"] == problem]
        if len(existing_of_problem) == 0:
            filtered_problems[problem] = []
        elif all(data["resolved"] for data in existing_of_problem) and \
            any(data["resolved_no_skip"] for data in existing_of_problem):
            continue
        else:
            filtered_problems[problem] = existing_of_problem
    return filtered_problems

def group_all_problems(all_problems):
    grouped_problems = dict()
    for problem in all_problems:
        folder = os.path.dirname(problem)
        if folder not in grouped_problems:
            grouped_problems[folder] = dict()
        grouped_problems[folder][problem] = all_problems[problem]
    return grouped_problems

def select_problems(grouped_problems, n_problems, folder_weights):
    """Selects problems from the given folders (i.e., competitions) based on the weights and the number of problems to select."""
    total_weight = sum(folder_weights.values())
    n_problems_per_unit = n_problems / total_weight
    # Initial number of problems per folder based on the weights
    n_problems_per_folder = {folder: math.ceil(weight * n_problems_per_unit) 
                             for folder, weight in folder_weights.items()}
    selected_problems = dict()
    remaining_folders = list(n_problems_per_folder.keys())
    remaining_folders = [folder for folder in remaining_folders if n_problems_per_folder[folder] > 0]
    # Some folders will have less problems than requested, so we need to adjust the number of problems per folder
    while any(n_problems_per_folder[folder] > len(grouped_problems.get(folder, [])) for folder in remaining_folders) \
        and len(remaining_folders) > 0:
        new_remaining_folders = []
        for folder in remaining_folders:
            # just add the entire folder if the number of problems requested is larger than the number of problems available
            if n_problems_per_folder[folder] > len(grouped_problems.get(folder, [])):
                for problem in grouped_problems.get(folder, dict()):
                    selected_problems[problem] = grouped_problems[folder][problem]
            else:
                new_remaining_folders.append(folder)
        remaining_folders = new_remaining_folders[:]
        if len(remaining_folders) == 0:
            break

        # recompute the number of problems per folder based on the remaining folders
        total_weight = sum(folder_weights[folder] for folder in remaining_folders)
        n_problems_per_unit = n_problems / total_weight
        n_problems_per_folder = {folder: math.ceil(folder_weights[folder] * n_problems_per_unit) 
                                 for folder in remaining_folders}
        
    # For folders that are big enough, first select the existing problems, then the non-existing ones
    # Existing problems are those that are already displayed on the website for a judge -> prefer to keep those
    for folder in remaining_folders:
        existing_problems = {
            problem: grouped_problems[folder][problem]
            for problem in grouped_problems.get(folder, dict())
            if grouped_problems[folder][problem]
        }
        non_existing_problems = {
            problem: grouped_problems[folder][problem]
            for problem in grouped_problems.get(folder, dict())
            if not grouped_problems[folder][problem]
        }
        for problem in list(existing_problems.keys())[:n_problems_per_folder[folder]]:
            selected_problems[problem] = existing_problems[problem]
        n_problems_per_folder[folder] -= len(existing_problems)
        if n_problems_per_folder[folder] <= 0:
            continue
        # If there are not enough existing problems, select non-existing ones
        list_non_existing = list(non_existing_problems.keys())
        random.shuffle(list_non_existing)
        for problem in list_non_existing[:n_problems_per_folder[folder]]:
            selected_problems[problem] = non_existing_problems[problem]
    
    return selected_problems

def assign_initial(selected_problems, judge_configs, weight_per_problem):
    problems_per_judge = dict()
    for problem in selected_problems:
        for existing in selected_problems[problem]:
            if existing["resolved"]:
                continue
            if existing["judge"] not in problems_per_judge:
                problems_per_judge[existing["judge"]] = []
            
            problems_per_judge[existing["judge"]].append(problem)
            judge_configs[existing["judge"]]["load"] -= weight_per_problem
            judge_configs[existing["judge"]]["load"] = max(judge_configs[existing["judge"]]["load"], 1e-6)
    
    return problems_per_judge

def assign_problems(project_config, judge_configs, selected_problems, weight_per_problem, problems_per_judge, config):
    """Assigns problems to judges based on the selected problems and the existing files."""

    # total_overshoots keeps track of how many problems need to be assigned twice to measure the human agreement rate
    n_overshoots = len([problem for problem in selected_problems 
                        if len([existing for existing in selected_problems[problem] 
                                if not existing["skipped"]]) > 1])
    total_overshoots = int(config.n_problems * config.overlap) - n_overshoots
    if config.ignore_overlap:
        total_overshoots = 0
    
    selected_problems_keys = list(selected_problems.keys())
    random.shuffle(selected_problems_keys)
    for i, problem in enumerate(selected_problems_keys):
        no_skipped = [existing for existing in selected_problems[problem] if not existing["skipped"]]
        if len(no_skipped) > 1:
            continue
        elif total_overshoots > 0 and len(no_skipped) == 1:
            n_to_add = 1
            total_overshoots -= 1
        elif total_overshoots > 0 and len(no_skipped) == 0:
            n_to_add = 2
            total_overshoots -= 1
        elif len(no_skipped) == 0:
            n_to_add = 1
        else:
            n_to_add = 0

        added = 0
        for _ in range(n_to_add):
            data = json.load(open(os.path.join(project_config.solved_base_folder, problem), "r"))
            for _ in range(100):
                judge_weights = {judge_id: judge_configs[judge_id] 
                                 for judge_id in judge_configs 
                                 if satisfies_constraints(data, judge_configs[judge_id], problem)}
                for judge_id in list(judge_weights.keys()):
                    if any(existing["judge"] == judge_id for existing in selected_problems[problem]):
                        del judge_weights[judge_id]
                    if judge_configs[judge_id].get("only_duplicates") and n_to_add == 1:
                        del judge_weights[judge_id]
                if len(judge_weights) == 0:
                    break
                weights = [val["load"] for val in judge_weights.values()]
                weights = [weight / sum(weights) for weight in weights]
                judge_id = random.choices(list(judge_weights.keys()), 
                                        weights=weights)[0]
                if judge_id not in problems_per_judge:
                    problems_per_judge[judge_id] = []
                if problem in problems_per_judge[judge_id]:
                    continue
                problems_per_judge[judge_id].append(problem)
                judge_configs[judge_id]["load"] -= weight_per_problem
                judge_configs[judge_id]["load"] = max(judge_configs[judge_id]["load"], 1e-6)
                added += 1
                break
        
        if added == 0 and n_to_add > 0:
            print(f"Could not add {problem} to any judge")
            if n_to_add == 2:
                total_overshoots += 1
        if added == 1 and n_to_add == 2:
            total_overshoots += 1

def assign_duplicate_only_judges(project_config, judge_configs, existing_file_data, 
                                 problems_per_judge, weight_per_problem):
    for judge in judge_configs:
        if judge not in problems_per_judge:
            problems_per_judge[judge] = []
        if judge_configs[judge].get("only_duplicates", False) and judge_configs[judge]["load"] > 1e-6:
            data = list(existing_file_data)
            random.shuffle(data)
            for problem in data:
                all_existing = [existing for existing in data if existing["problem"] == problem["problem"]]
                if len(all_existing) > 1:
                    continue
                if problem["judge"] == judge or problem["problem"] in problems_per_judge[judge]:
                    continue
                if not satisfies_constraints(json.load(open(os.path.join(project_config.solved_base_folder, 
                                                                         problem["problem"]), "r")), 
                                             judge_configs[judge], problem["problem"]):
                    continue
                problems_per_judge[judge].append(problem["problem"])
                judge_configs[judge]["load"] -= weight_per_problem
                if judge_configs[judge]["load"] < 1e-6:
                    break


def add_files(project_config, judge_configs, problems_per_judge):
    for judge_id in judge_configs:
        if judge_id not in problems_per_judge:
            problems_per_judge[judge_id] = []
        for problem in problems_per_judge[judge_id]:
            # create the folder if it does not exist
            os.makedirs(os.path.join(project_config.website_folder, judge_id, os.path.dirname(problem)), exist_ok=True)
            # copy the file to the new location
            if not os.path.exists(os.path.join(project_config.website_folder, judge_id, problem)):
                os.system(f"cp {project_config.solved_base_folder}/{problem} {os.path.join(project_config.website_folder, judge_id, problem)}")
            else:
                data_solved = json.load(open(f"{project_config.solved_base_folder}/{problem}", "r"))
                data_judged = json.load(open(os.path.join(project_config.website_folder, judge_id, problem), "r"))
                if len(data_solved["attempts"]) > len(data_judged["attempts"]):
                    for attempt in data_solved["attempts"]:
                        if attempt["model_id"] not in [a["model_id"] for a in data_judged["attempts"]]:
                            data_judged["attempts"].append(attempt)
                for attempt in data_solved["attempts"]:
                    for attempt2 in data_judged["attempts"]:
                        if attempt2["model_id"] == attempt["model_id"]:
                            attempt2["llm_judgment"] = attempt.get("llm_judgment", None)

                with open(os.path.join(project_config.website_folder, judge_id, problem), "w") as f:
                    json.dump(data_judged, f, indent=4)

def remove_files(project_config, judge_configs, problems_per_judge):
    for judge_id in judge_configs:
        existing_files = glob.glob(os.path.join(project_config.website_folder, judge_id, "**/*.json"), recursive=True)
        for file in existing_files:
            simple_file_name = file.replace(project_config.website_folder + "/" + judge_id + "/", "")
            if simple_file_name not in problems_per_judge[judge_id]:
                solved_file = os.path.join(project_config.solved_base_folder, simple_file_name)
                if not os.path.exists(solved_file):
                    continue # from another project
                data = json.load(open(file, "r"))
                if not fully_resolved(data) and not fully_not_resolved(data):
                    continue # not fully resolved, so we keep it, judge can keep judging it
                os.remove(file)
                logger.info(f"Removed {file} from {judge_id} as it is not in the selected problems")

def log_data(project_config, judge_configs, problems_per_judge):
    for judge_id in judge_configs:
        # log the amount of problems for each judge
        logger.info(f"Judge {judge_id} has {len(problems_per_judge[judge_id])} problems")
        overlapped_problems = []
        for second_judge_id in judge_configs:
            if second_judge_id == judge_id:
                continue
            for problem in problems_per_judge[second_judge_id]:
                if problem in problems_per_judge[judge_id]:
                    overlapped_problems.append(problem)
        logger.info(f"Judge {judge_id} has {len(overlapped_problems)} overlapped problems with other judges")

        glob_already_judged = glob.glob(os.path.join(project_config.judged_base_folder, judge_id, "**/*.json"), recursive=True)
        problems_already_judged = [file.replace(os.path.join(project_config.judged_base_folder, judge_id) + "/", "") 
                                   for file in glob_already_judged]

        for problem in problems_per_judge[judge_id]:
            if problem in problems_already_judged:
                data_on_website = json.load(open(os.path.join(project_config.website_folder, judge_id, problem), "r"))
                if all(attempt["grading"] is not None for attempt in data_on_website["attempts"]):
                    continue
                logger.warning(f"Problem {problem} is already judged by {judge_id}")

def distribute_discrepancies(project_config):
    all_data = load_judged_data(project_config.judged_base_folder)
    overlapping_scores = identify_overlapping_judgments(all_data)

    if len(overlapping_scores) == 0:
        return
    all_data_processed = dict()
    for sample in overlapping_scores:
        if sample["is_equal"]:
            continue
        judge1_data = all_data[sample["judge"]][sample["file_name"]][sample["run"]]
        judge2_data = all_data[sample["judge2"]][sample["file_name"]][sample["run2"]]
        raw_file_data = json.load(open(os.path.join(project_config.solved_base_folder, 
                                                    sample["file_name"]), "r"))
        raw_file_data["attempts"] = [
            {
                "model_id": judge1_data["model"],
                "grading": {
                    "details": [
                        {
                            "part_id": dict_1["part_id"],
                            "score": dict_1["score"],
                            "feedback": dict_1["feedback"],
                            "existing_judgments": [
                                {
                                    "judge": sample["judge"],
                                    "score": dict_1["score"],
                                    "feedback": dict_1["feedback"],
                                    "annotations": dict_1.get("annotations", []),
                                },
                                {
                                    "judge": sample["judge2"],
                                    "score": judge2_data["grading"]["details"][i]["score"],
                                    "feedback": judge2_data["grading"]["details"][i]["feedback"],
                                    "annotations": judge2_data["grading"]["details"][i].get("annotations", []),
                                }
                            ]
                        } for i, dict_1 in enumerate(judge1_data["grading"]["details"])
                    ],
                    "score": judge1_data["score"],
                    "uncertain": judge1_data["uncertain"] or judge2_data["uncertain"],
                    "no_feedback": judge1_data["no_feedback"] or judge2_data["no_feedback"],
                    "long": judge1_data.get("long", False) or judge2_data.get("long", False),
                },
                "solution": judge1_data["solution"],
            },
        ]

        if sample["file_name"] not in all_data_processed:
            all_data_processed[sample["file_name"]] = raw_file_data
        else:
            all_data_processed[sample["file_name"]]["attempts"].append(raw_file_data["attempts"][0])

    for file_name, raw_file_data in all_data_processed.items():
        for judge_id in project_config.admins:
            os.makedirs(os.path.join(project_config.website_folder, judge_id, project_config.discrepancies_slug), exist_ok=True)
            with open(os.path.join(project_config.website_folder, judge_id, project_config.discrepancies_slug, file_name.replace("/", "__")), "w") as f:
                json.dump(raw_file_data, f, indent=4)

def distribute_issues(project_config):
    all_files = glob.glob(os.path.join(project_config.website_folder, "**/*.json"), recursive=True)
    all_files += glob.glob(os.path.join(project_config.judged_base_folder, "**/*.json"), recursive=True)

    for file in all_files:
        
        filename = file.replace(project_config.website_folder + "/", "")
        filename = filename.replace(project_config.judged_base_folder + "/", "")
        solved_filename = "/".join(filename.split("/")[1:])  # remove the first folder
        solved_filename = os.path.join(project_config.solved_base_folder, solved_filename)

        if not os.path.exists(solved_filename):
            continue

        data = json.load(open(file, "r"))
        filename = "/".join(filename.split("/")[1:]).replace("/", "__")
        if "issue" in data and data["issue"] is not None:
            data["issue_other_judge"] = {
                "issue": data["issue"],
            }
            del data["issue"]
            for admin in project_config.admins:
                path = os.path.join(project_config.website_folder, admin, project_config.problems_slug)
                os.makedirs(path, exist_ok=True)
                with open(os.path.join(path, filename), "w") as f:
                    json.dump(data, f, indent=4)
        if any(solution.get("issue") is not None for solution in data.get("solutions", [])):
            for solution in data.get("solutions", []):
                if solution.get("issue") is None:
                    continue
                solution["issue_other_judge"] = {
                    "issue": solution["issue"]
                }
                del solution["issue"]

            for admin in project_config.admins:
                path = os.path.join(project_config.website_folder, admin, project_config.solutions_slug)
                os.makedirs(path, exist_ok=True)
                with open(os.path.join(path, filename), "w") as f:
                    json.dump(data, f, indent=4)

def load_judges(project_config, config):
    judge_configs = dict()

    basic_json = json.load(open(project_config.judge_file, "r"))

    json_config = json.load(open(config.judge_file, "r"))

    for sample in basic_json:
        if sample["id"] not in json_config:
            continue

        judge_configs[sample["id"]] = {
            **sample,
            **json_config[sample["id"]],
        }
        if judge_configs[sample["id"]].get("load", 1) <= 0:
            del judge_configs[sample["id"]]
    
    return judge_configs

def distribute(project_config, config, only_admin=False):

    os.makedirs(project_config.judged_base_folder, exist_ok=True)

    recover(project_config)

    judge_configs = load_judges(project_config, config)

    if not only_admin:
        all_judge_ids = list(judge_configs.keys())
        all_problems = get_all_problems(project_config)
        existing_file_data = find_existing_files(project_config, all_judge_ids)
        all_problems = filter_all_problems(all_problems, existing_file_data)
        all_problems = group_all_problems(all_problems)

        selected_problems = select_problems(all_problems, config.n_problems, config.competition_weight)
        
        total_weight = sum(judge_config["load"] for judge_config in judge_configs.values())
        weight_per_problem = total_weight / (config.n_problems * (1 + config.overlap))
        problems_per_judge = assign_initial(selected_problems, judge_configs, weight_per_problem)

        assign_problems(project_config, judge_configs, selected_problems, weight_per_problem, problems_per_judge, config)
        assign_duplicate_only_judges(project_config, judge_configs, existing_file_data, problems_per_judge, weight_per_problem)

        # exit()
        add_files(project_config, judge_configs, problems_per_judge)
        remove_files(project_config, judge_configs, problems_per_judge)

        # log all information
        log_data(project_config, judge_configs, problems_per_judge)
    distribute_discrepancies(project_config)
    distribute_issues(project_config)