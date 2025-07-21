import argparse
from grading.configs import load_config
import os
import glob
from grading.postprocess import process_sample, join
import json
import numpy as np

def convert_grading(grading, grading_scheme, points):
    converted_grading = dict()
    converted_grading["points"] = grading["score"]
    converted_grading["max_points"] = points
    converted_grading["details"] = []

    for i, part in enumerate(grading["details"]):
        corresponding_part = [
            p for p in grading_scheme if p["part_id"] == part["part_id"]
        ][0]
        part_converted = {
            "desc": part["feedback"],
            "points": part["score"],
            "max_points": corresponding_part["points"],
            "grading_scheme_desc": corresponding_part["description"],
            "title": corresponding_part["title"],
        }
        converted_grading["details"].append(part_converted)
    return converted_grading



if __name__ == "__main__":
    # Set a random seed for reproducibility
    parser = argparse.ArgumentParser(description="Convert MathArena problems to a different format.")
    parser.add_argument("--project", help="Name of the project to convert.")
    parser.add_argument("--config-base", default="configs/projects", help="Base folder for the config files.")
    parser.add_argument("--output-folder", default="data/converted_problems", help="Folder to save the converted problems.")

    args = parser.parse_args()

    project_config = load_config(os.path.join(args.config_base, f"{args.project}.yaml"))

    solver_config = load_config(project_config.solver_config)

    if not os.path.exists(args.output_folder):
        os.makedirs(args.output_folder)

    all_files = glob.glob(f"{project_config.judged_base_folder}/**/*.json", recursive=True)

    all_samples = []

    for file_name in all_files:
        judge_id = file_name.replace(project_config.judged_base_folder, "").split("/")[1]
        samples = process_sample(file_name, judge_id)
        all_samples.extend(samples)

    all_samples = join(all_samples)

    matharena_samples = dict()

    for sample in all_samples:
        if "_" in sample["problem_id"]:
            sample["problem_id"] = sample["problem_id"].split("_")[-1]  # Remove suffix if present
        id_ = int(sample["problem_id"]) - 1
        model_id = sample["model_id"]
        if model_id not in matharena_samples:
            matharena_samples[model_id] = dict()
        if id_ not in matharena_samples[model_id]:
            matharena_samples[model_id][id_] = {
                "idx": int(id_),
                "problem": sample["problem"],
                "gold_answer": None,
                "anonymous_id": "123456",
                
                "pass_at_1": 0,
                "cost": None,
                "messages": [],
                "answers": [],
                "correct": [],
                "detailed_costs": [],
                "warnings": [],
                "judgment": [
                    [] for _ in range(len(sample["grading"]))  # Initialize with empty lists for each grading
                ]
            }
        answer = sample["solution"]
        matharena_samples[model_id][id_]["messages"].append([
            {
                "role": "user",
                "content": solver_config.prompt.format(problem=sample["problem"])
            },
            {
                "role": "assistant",
                "content": answer
            }
        ])
        matharena_samples[model_id][id_]["detailed_costs"].append(sample["cost"])
        matharena_samples[model_id][id_]["warnings"].append(0)
        matharena_samples[model_id][id_]["answers"].append(None)
        avg_score = sum([g["score"] for g in sample["grading"]]) / len(sample["grading"])
        avg_score_01 = avg_score / sample["points"]
        matharena_samples[model_id][id_]["correct"].append(avg_score_01)
        converted_grading_list = [
            convert_grading(g, sample["grading_scheme"], sample["points"]) for g in sample["grading"]
        ]
        for i, converted_grading in enumerate(converted_grading_list):
            matharena_samples[model_id][id_]["judgment"][i].append(converted_grading)

    for model_id, problems in matharena_samples.items():
        
        os.makedirs(os.path.join(args.output_folder, model_id), exist_ok=True)
        for id_, problem in problems.items():
            matharena_samples[model_id][id_]["pass_at_1"] = np.mean(matharena_samples[model_id][id_]["correct"])
            matharena_samples[model_id][id_]["cost"] = {
                "cost": float(np.sum([c["cost"] 
                                      for c in matharena_samples[model_id][id_]["detailed_costs"]])),
                "output_tokens": float(np.sum([c["output_tokens"] 
                                               for c in matharena_samples[model_id][id_]["detailed_costs"]])),
                "input_tokens": float(np.sum([c["input_tokens"] 
                                              for c in matharena_samples[model_id][id_]["detailed_costs"]])),
            }
            output_file = os.path.join(args.output_folder, model_id, f"{id_ + 1}.json")
            with open(output_file, "w") as f:
                json.dump(problem, f, indent=4)
            print(f"Converted problem {id_} for model {model_id} saved to {output_file}")




