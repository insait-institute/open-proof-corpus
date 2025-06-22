import json
import os
import glob
import pandas as pd

test_problem_ids = ['BMOSL_2016_10', 'BMOSL_2016_14', 'BMOSL_2016_9', 'BMOSL_2018_8',
       'BMOSL_2021_13', 'BalticWay_2010_11', 'BalticWay_2011_5',
       'BalticWay_2017_2', 'BalticWay_2018_11', 'BalticWay_2021_9',
       'EGMO_2012_8', 'EGMO_2013_1', 'EGMO_2020_2', 'IMC_2023_3',
       'IMC_2024_10', 'IMOSL_2001_11', 'IMOSL_2002_4', 'IMOSL_2002_9',
       'IMOSL_2003_27', 'IMOSL_2007_21', 'IMOSL_2011_17', 'IMOSL_2012_16',
       'IMOSL_2012_22', 'IMOSL_2014_20', 'IMOSL_2017_16', 'IMOSL_2019_9',
       'IMOSL_2021_31', 'IMOSL_2022_1', 'IMOSL_2022_32', 'JMO_2012_1',
       'JMO_2016_4', 'JMO_2017_3', 'JMO_2018_1', 'JMO_2019_3',
       'RMM_Extralist_2018_5', 'RMM_Extralist_2018_7',
       'RMM_Extralist_2020_5', 'USAMO_2006_1', 'USAMO_2018_3',
       'USAMO_2018_5', 'bmo1_2009_4', 'bmo1_2009_5', 'bmo1_2015_4',
       'bmo1_2016_5', 'bmo1_2024_1', 'bmo2_2010_2', 'bmo2_2019_2',
       'bulgarian-EMT_2022_10_2', 'bulgarian-PMS_2001_11_3',
       'bulgarian-PMS_2002_8_2', 'bulgarian-ZMS_2011_12_3',
       'bulgarian-ZMS_2021_12_1', 'bulgarian-ZMS_2023_11_1',
       'irish_2010_6', 'irish_2014_5', 'irish_2016_4', 'irish_2021_4',
       'izho_2012_1', 'izho_2015_6', 'izho_2016_4', 'izho_2018_2',
       'izho_2019_3', 'izho_2023_4', 'putnam_2013_a1', 'putnam_2017_a5',
       'putnam_2020_b2']

def identify_split(data):
    if "attempts_singular" in data:
        return "best_of_n"
    elif len(data["attempts"]) > 7:
        return "pass_at_n"
    elif data["problem_id"].startswith("matharena_"):
        return "matharena"
    elif data["metadata"].get("url", "").startswith("https://raw.githubusercontent.com/trishullab/PutnamBench/"):
        return "putnambench"
    elif data["problem_id"] in test_problem_ids:
        return "test"
    else:
        return "generic"
    
def flatten_attempt(attempt):
    grading = attempt.get("grading", {})
    if grading is None:
        grading = {}
    llm_issues = attempt.get("llm_judgment", None)
    if llm_issues is None:
        llm_issues = {"result": dict()}
    llm_issues = llm_issues["result"]
    no_feedback_or_long = grading.get("no_feedback", False) or grading.get("long", False)
    if no_feedback_or_long:
        return None
    return {
        "model_id": attempt["model_id"],
        "solution": attempt["solution"],
        "thinking": attempt.get("thinking", None),
        "judge_data": attempt.get("judge_data", None),
        "cost": attempt["cost"]["cost"],
        "output_tokens": attempt["cost"]["output_tokens"],
        "input_tokens": attempt["cost"]["input_tokens"],
        "score": grading.get("score", None),
        "uncertain": grading.get("uncertain", False),
        "feedback": grading.get("details", [{"feedback": None}])[0]["feedback"],
        "annotations": attempt["annotations"],
        "timestamp": attempt["timestamp"],
        "llm_summary": llm_issues.get("summary", None),
        "llm_issues": llm_issues.get("issues", None),
        "other_selectors": [
            {
                "model_id": other_selector["model_id"],
                "cost": other_selector["cost"]["cost"],
                "output_tokens": other_selector["cost"]["output_tokens"],
                "input_tokens": other_selector["cost"]["input_tokens"],
                "judge_data": other_selector.get("judge_data", None),
            } for other_selector in attempt.get("other_selectors", [])
        ] if "other_selectors" in attempt else None,
    }

def flatten_file(data, judge_id):
    split = identify_split(data)
    # hash the judge id for some extra anonymity
    flattened_data = []

    gt_solution = data["solutions"][0]["solution"] if data["solutions"] else None
    gt_issue = data["solutions"][0].get("issue", None) if data["solutions"] else None
    gt_note = data["solutions"][0].get("note", None) if data["solutions"] else None

    if "difficulty" in data["metadata"]:
        del data["metadata"]["difficulty"]
    if "competition" in data["metadata"]:
        del data["metadata"]["competition"]
    if data.get("useless", False):
        return []
    flattened_base = {
        "problem_id": data["problem_id"],
        "competition": data["problem_id"].split("_")[0],
        "problem_issue": data.get("issue", None),
        **data["metadata"],
        "judge_id": judge_id,
        "split": split,
        "problem": data["problem"],
        "ground_truth_solution": gt_solution,
        "ground_truth_issue": gt_issue,
        "ground_truth_note": gt_note,
        "attempts_singular": [
            {
                "model_id": attempt["model_id"],
                "solution": attempt["solution"],
                "cost": attempt["cost"]["cost"],
                "output_tokens": attempt["cost"]["output_tokens"],
                "input_tokens": attempt["cost"]["input_tokens"],
                "index": i
            } for i, attempt in enumerate(data.get("attempts_singular", []))
        ],
    }

    for attempt in data["attempts"]:
        flattened_attempt = flatten_attempt(attempt)
        if flattened_attempt is None:
            continue
        flattened_data.append({**flattened_base, **flattened_attempt})

    return flattened_data

def process_files():
    data = []
    for file_path in glob.glob("data/judged/**/*.json", recursive=True):
        if file_path.startswith("data/judged/usamo_2025/") or file_path.startswith("data/judged/test/"):
            continue
        with open(file_path, "r") as f:
            file_data = json.load(f)
            judge_id = file_path.split("/")[3]  # Extract judge ID from the file path
            flattened_data = flatten_file(file_data, judge_id)
            data.extend(flattened_data)
    return data

def merge_double_judgments(df: pd.DataFrame) -> pd.DataFrame:
    # Columns you want to roll up into lists
    key_cols = ["problem_id", "solution"]

    # columns you want to roll up into lists
    judgment_cols = [
        "score",
        "uncertain",
        "feedback",
        "annotations",
        "judge_id",
    ]

    # everything else should stay as-is
    other_cols = [c for c in df.columns if c not in key_cols + judgment_cols]

    # build an aggregation dictionary
    agg_funcs = {c: list for c in judgment_cols}
    agg_funcs.update({c: "first" for c in other_cols})

    # perform the grouping
    merged = (
        df.groupby(key_cols, as_index=False, sort=False, dropna=False)
          .agg(agg_funcs)
    )

    return merged



data = process_files()

output_file = "data/judged_data.json"
    
data = pd.DataFrame(data)
data = merge_double_judgments(data)
data.to_json(output_file, orient="records", lines=True)