import os
import json
import re
import argparse
from grading.configs import load_config
from datetime import datetime

parser = argparse.ArgumentParser(description="Process problems.")
parser.add_argument("--project", help="Project name to process.")
parser.add_argument("--file-name", default="sample.json", help="Name of the file to process.")
parser.add_argument("--config-base", default="configs/projects", help="Base directory for project configurations.")
args = parser.parse_args()

project_config = load_config(os.path.join(args.config_base, args.project + ".yaml"))
data = json.load(open(os.path.join(project_config.raw_base_folder, args.file_name), "r"))

for i, item in enumerate(data):
    # Create a directory for each item
    item["grading_scheme"] = [
        {
            "part_id": 1,
            "title": "Correctness",
            "description": "<p>A solution should be considered correct even if it would earn 5+/7 points in a full grading. Examples of small penalties worth 1 point are if the solution: <ul><li>Makes a small computational mistake that can be easily fixed</li><li>Misses an edge case which can be easily proven/disproven</li><li>Skips over a step that follows without much reasoning or manual work</li></ul> A solution should be marked as incorrect if: <ul><li>It marks a step as trivial, if it is not immediately obvious why this would be the case</li><li>It omits algebra-heavy computational steps, regardless of whether or not it has outlined the methodology</li><li>Generalizes over a pattern without rigorously describing the pattern, or without proving any relevant properties.</li><li>It cites a non-existing or unpopular source/Theorem, which cannot be immediately found from searching for it online. Thus, any theorems that can be immediately found and have a Wikipedia article are allowed.</li></ul> The model has been specifically told that it should not skip steps or mark them as trivial. Any violation of this rule should be considered by assuming the model does not know how to derive the &quot;trivial&quot; step</p>",
            "points": 1
        }
    ]
    item["points"] = 1
    for solution in item["solutions"]:
        # find all links in the format ![](https://cdn*), remove the link, and add it to the "images" key
        link_regex = r"!\[\]\((https://cdn.*?)(\s|$)"
        matches = re.findall(link_regex, solution["solution"])
        solution["solution"] = re.sub(link_regex, "", solution["solution"])
        solution["images"] = {
            f"Figure {i + 1}": match[0][:-1] for i, match in enumerate(matches)
        }

    item["date_added"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    splitted_problem_id = item['problem_id'].split("_")
    folder_name = splitted_problem_id[0]
    folder_name = folder_name.replace(" ", "_")
    filename = "_".join(splitted_problem_id[1:])
    filename = filename.replace("/", "_")
    filename = filename.replace(" ", "_")
    os.makedirs(os.path.join(project_config.unsolved_base_folder, folder_name), exist_ok=True)
    json.dump(item, open(os.path.join(project_config.unsolved_base_folder, folder_name, f"{filename}.json"), "w"), indent=4)
