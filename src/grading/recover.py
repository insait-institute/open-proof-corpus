from bs4 import BeautifulSoup
from thefuzz import fuzz
import json
import glob
import os
from .configs import load_config

def fully_resolved(data):
    if data.get("useless"):
        return True
    for attempt in data["attempts"]:
        if attempt["grading"] is None:
            return False
        if attempt["grading"]["no_feedback"] or attempt["grading"].get("long", False):
            continue
        if attempt["grading"]["score"] is None:
            return False
        if any(rubric["score"] is None for rubric in attempt["grading"]["details"]):
            return False
        if any(rubric["feedback"] is None for rubric in attempt["grading"]["details"]):
            return False
    return True

def recover(project_config, remove=False):
    all_problem_files = glob.glob(os.path.join(project_config.website_folder, "**/*.json"), recursive=True)
    distribution_config = load_config(project_config.distribution_config)
    judge_file = json.load(open(distribution_config.judge_file, "r"))
    judge_ids = list(judge_file.keys())

    for file in all_problem_files:
        solved_filename = file.replace(project_config.website_folder + "/", "")
        if not any(solved_filename.startswith(judge_id + "/") for judge_id in judge_ids):
            continue
        solved_filename = "/".join(solved_filename.split("/")[1:])
        solved_filename = os.path.join(project_config.solved_base_folder, solved_filename)
        new_filename = file.replace(project_config.website_folder, project_config.judged_base_folder)
        if not os.path.exists(solved_filename):
            continue
        
        data = json.load(open(file, "r"))
        if "attempts" not in data:
            continue
        if not fully_resolved(data):
            continue

        if os.path.exists(new_filename):
            data_old = json.load(open(new_filename, "r"))
            ## if data_old is data, except that data_old might have more fields, skip
            for attempt in data_old["attempts"]:
                if attempt["annotations"] is None:
                    continue
                for annotation in attempt["annotations"]:
                    if "original_text" in annotation:
                        del annotation["original_text"]
                        del annotation["original_text_indices"]
            if data_old == data:
                if remove:
                    os.remove(file)
                continue

        for attempt in data["attempts"]:
            if attempt["annotations"] is None:
                continue
            for annotation in attempt["annotations"]:
                if "original_text" in annotation:
                    continue
                selected_text, indices = match_text(
                    annotation["selected_text"],
                    attempt["solution"],
                    n_equations_before=annotation.get("n_equations_before", 0),
                    n_equations=annotation.get("n_equations", 0)
                )
                if selected_text is not None:
                    annotation["original_text"] = selected_text
                    annotation["original_text_indices"] = indices
                else:
                    print(f"Could not match text for {file} attempt {attempt['model_id']} annotation {annotation['id']}")
                    annotation["original_text"] = None
                    annotation["original_text_indices"] = (0, 0)
        
        
        if not os.path.exists(os.path.dirname(new_filename)):
            os.makedirs(os.path.dirname(new_filename), exist_ok=True)

        with open(new_filename, "w") as f:
            json.dump(data, f, indent=4)
        if remove:
            os.remove(file)

def match_text(
    selected_browser_text: str,
    original_text: str,
    n_equations_before: int = 0,
    n_equations: int = 0,
):  
    if selected_browser_text.startswith("<span class="):
        # parse soup
        soup = BeautifulSoup(selected_browser_text, "html.parser")
        selected_browser_text = soup.get_text()
    # Step 1. Normalize the selected text and original text
    start_index = None
    end_index = -1
    count_now = 0
    for i in range(0, len(original_text) - 1):
        if original_text[i] == "$" and original_text[i + 1] != "$":
            count_now += 0.5
        elif original_text[i:i+2] == "\\)" or original_text[i:i+2] == "\\]":
            count_now += 1
        if count_now >= n_equations_before and start_index is None:
            start_index = i
        if count_now >= n_equations_before + n_equations + 1:
            end_index = i
            break
    if start_index is None:
        start_index = 0
    original_text_selected, original_text_indices = look(
        selected_browser_text,
        original_text,
        start_index,
        end_index,
        limit=0.7
    )
    if original_text_selected is None:
        original_text_selected, original_text_indices = look(
            selected_browser_text,
            original_text,
            0,
            len(original_text),
            limit=0.7
        )
    return original_text_selected, original_text_indices
    

def look(selected_browser_text, original_text, start_index, end_index, limit=0.9):
    highest_ratio = 0
    highest_ratio_indices = (0, 0)
    min_length = len(selected_browser_text) // 2
    max_length = len(selected_browser_text) * 2
    max_length = max(max_length, 20)  # Ensure max_length is at least 20
    for i in range(start_index, end_index):
        for j in range(i + 1 + min_length, min(end_index + 1, i + max_length)):
            ratio = fuzz.ratio(selected_browser_text, original_text[i:j])
            if ratio > highest_ratio:
                highest_ratio = ratio
                highest_ratio_indices = (i, j)
    if highest_ratio >= limit * 100:
        return original_text[highest_ratio_indices[0]:highest_ratio_indices[1]], highest_ratio_indices
    return None, None