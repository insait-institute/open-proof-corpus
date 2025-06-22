import re
import sympy
from sympy.parsing.latex import parse_latex
import os
import json
import glob


def latex2sympy_fixed(latex: str):
    # if _integer is present, replace it with _{integer} for any integer
    latex = re.sub(r"_([0-9]+)", r"_{\1}", latex)
    latex_parsed = parse_latex(latex)
    # replace constants like pi and e with their numerical value
    known_constants = {'pi': sympy.pi, 'e': sympy.E}

    # Replace any symbol in expr that is in our known_constants dictionary.
    expr = latex_parsed.xreplace({s: known_constants[s.name]
                        for s in latex_parsed.free_symbols
                        if s.name in known_constants})
    return expr
  
def get_latex_array(mat: list[list[str]]) -> str:
    n_cols = len(mat[0])
    cs = "{" + "c" * n_cols + "}"
    return "\\begin{array}" + cs + "\n" + "\n".join([" & ".join(row) + " \\\\" for row in mat]) + "\n\\end{array}"

def convert_to_int(obj):
    if isinstance(obj, str):
        return int(obj)
    if isinstance(obj, list):
        return [convert_to_int(item) for item in obj]
    raise ValueError(f"Cannot convert {type(obj)} to int")


def load_judged_data(dir, regexes=None):
    all_data = {}

    for folder in os.listdir(dir):
        all_data[folder] = {}
        glob_files = glob.glob(os.path.join(dir, folder, "**/*.json"), recursive=True)

        if regexes is not None:
            glob_files = [
                file for file in glob_files
                if any(re.match(regex, file.replace(f"{dir}/{folder}/", "")) for regex in regexes)
            ]

        for file in glob_files:
            file_name = file.replace(f"{dir}/{folder}/", "")
            data_file = []
            raw_data = json.load(open(file, "r"))
            for attempt in raw_data["attempts"]:
                if "grading" not in attempt or attempt["grading"] is None or attempt["grading"]["score"] is None:
                    continue
                grading = attempt["grading"]
                data_file.append({
                    "model": attempt["model_id"],
                    "metadata": raw_data.get("metadata", {}),
                    "score": grading["score"],
                    "uncertain": grading["uncertain"],
                    "no_feedback": grading["no_feedback"],
                    "long": grading.get("long", False),
                    "grading": grading,
                    "solution": attempt["solution"],
                    "problem_issue": raw_data.get("issue") is not None
                })
            all_data[folder][file_name] = data_file

    return all_data

def identify_overlapping_judgments(all_data):
    overlapping_scores = []
    judges_list = list(all_data.keys())
    for i, judge in enumerate(judges_list):
        for j in range(i + 1, len(judges_list)):
            judge2 = judges_list[j]
            for file_name in all_data[judge]:
                if file_name in all_data[judge2]:
                    for k, attempt in enumerate(all_data[judge][file_name]):
                        for k2, attempt2 in enumerate(all_data[judge2][file_name]):
                            if attempt["model"] != attempt2["model"] or attempt["solution"] != attempt2["solution"]:
                                continue
                            uncertain = attempt2["uncertain"] or attempt2["uncertain"]
                            if attempt2["no_feedback"] or attempt["no_feedback"]:
                                continue
                            if attempt2["long"] or attempt["long"]:
                                continue
                            is_equal = attempt["score"] == attempt2["score"]
                            overlapping_scores.append({
                                "judge": judge,
                                "judge2": judge2,
                                "file_name": file_name,
                                "run": k,
                                "run2": k2,
                                "uncertain": uncertain,
                                "is_equal": is_equal
                            })

    return overlapping_scores

def extract_solution(text: str, only_numeric = False) -> str:
    start_tag = r'\boxed{'
    start = text.rfind(start_tag)
    if start == -1:
        return "none" if not only_numeric else "0"

    i = start + len(start_tag)
    depth = 1
    while i < len(text) and depth:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1

    if depth:                       # never balanced → abort
        return "none" if not only_numeric else "0"

    sol = text[start + len(start_tag) : i - 1]  # slice inside the braces

    while True:
        new_sol = re.sub(r'\\text\s*\{([^{}]*)\}', r'\1', sol)
        if new_sol == sol:          # nothing left to unwrap
            break
        sol = new_sol

    sol = re.sub(r'\s+', '', sol).lower()
    if only_numeric: # only keep numeric and "."
        sol = re.sub(r'[^0-9.]', '', sol)
        if not sol:
            sol = "0"
    return sol