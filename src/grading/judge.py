from .api import APIQuery
from .configs import *
from .matching import fuzzy_substring_pos

import os
import re
import json
from datetime import datetime
from loguru import logger
import re
from tqdm import tqdm

# Compile once so it’s readable and fast
BAD_ESCAPE_RE = re.compile(
    r'''
    (?<!\\)     # the \ is NOT preceded by another backslash
    \\          # the \ we want to test
    (?!         # it is NOT followed by any valid JSON escape
        ["\\/bfnrtu]   # "  \  /  b  f  n  r  t  u
    )
    ''',
    re.VERBOSE,
)

def extract_json(model_output: str) -> dict | None:
    json_pattern = r'```json\n(.*?)\n```'
    match = re.search(json_pattern, model_output, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        json_str = model_output.strip()

    if not json_str:
        logger.warning("Extracted JSON string is empty.")
        return None
    
    def escape_newlines_in_json_strings(text):
        out = []
        last_idx = 0
        for match_obj in re.finditer(r'"((?:\\.|[^"\\])*)"', text):
            start, end = match_obj.span()
            out.append(text[last_idx:start])
            string_content = match_obj.group(1)
            escaped_string_content = string_content.replace('\r\n', '\\r\\n').replace('\n', '\\n').replace('\r', '\\r')
            out.append(f'"{escaped_string_content}"')
            last_idx = end
        out.append(text[last_idx:])
        return "".join(out)

    if (json_str.startswith('{') and json_str.endswith('}')) or \
       (json_str.startswith('[') and json_str.endswith(']')):
        json_str = escape_newlines_in_json_strings(json_str)

    try:
        json_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        # Fix single backslashes not part of known escape sequences
        processed_json_str = BAD_ESCAPE_RE.sub(r'\\\\', json_str)
        try:
            json_data = json.loads(processed_json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Fallback decoding failed")
            return None

    if not isinstance(json_data, dict):
        logger.warning("Parsed JSON is not a dictionary.")
        return None
    if "summary" not in json_data:
        logger.warning("JSON does not contain 'summary' key.")
        return None
    if "issues" not in json_data:
        logger.warning("JSON does not contain 'issues' key.")
        return None
    if not isinstance(json_data["issues"], list):
        logger.warning("'issues' key is not a list.")
        return None

    for i, issue in enumerate(json_data["issues"]):
        if not isinstance(issue, dict):
            logger.warning(f"Issue at index {i} is not a dictionary.")
            return None
        if not ("location" in issue and "description" in issue and "category" in issue):
            logger.warning(f"Issue at index {i} missing required keys. Issue: {issue}")
            return None
    return json_data

def judge(project_config : OverallConfig, llm_judge_config : SolverConfig, 
          files_to_run : List[str], overwrite: bool = False):
    total_cost = 0
    config = load_config(os.path.join(project_config.model_config_folder, llm_judge_config.model + ".yaml"))
    del config["human_readable_id"]
    if "date" in config:
        del config["date"]

    for i in range(llm_judge_config.n_attempts):
        queries, metadata = build_queries(files_to_run, llm_judge_config.prompt, 
                                          llm_judge_config.overwrite and i == 0)

        querier = APIQuery(
            **config
        )
        total_cost = 0
        n_finished_queries = 0
        for idx, result, cost in querier.run_queries(queries):
            total_cost += cost["cost"]
            n_finished_queries += 1
            if n_finished_queries % 20 == 0:
                logger.info(f"Finished {n_finished_queries} queries, total cost: {total_cost:.2f}")
            
            if result is None or len(result) == 0:
                logger.warning(f"Query {idx} returned no result.")
                continue

            json_data = extract_json(result)

            if json_data is None:
                continue

            with open(metadata[idx]["file"], "r") as f:
                problem = json.load(f)
            
            problem["attempts"][metadata[idx]["attempt_index"]]["llm_judgment"] = {
                "result": json_data,
                "timestamp": datetime.now().isoformat()
            }

            with open(metadata[idx]["file"], "w") as f:
                json.dump(problem, f, indent=4)
    
    postprocess(files_to_run)
    return total_cost

def postprocess(files_to_run):
    for file in tqdm(files_to_run):
        with open(file, "r") as f:
            problem = json.load(f)
        
        for attempt in problem["attempts"]:
            if attempt.get("llm_judgment", None) is None:
                continue
            
            for issue in attempt["llm_judgment"]["result"]["issues"]:
                if issue.get("text", None):
                    indices = fuzzy_substring_pos(
                        attempt["solution"],
                        issue["text"],
                    )
                    if indices is None:
                        issue["start_index"] = None
                        issue["end_index"] = None
                    else:
                        issue["start_index"] = indices[0]
                        issue["end_index"] = indices[1]

        with open(file, "w") as f:
            json.dump(problem, f, indent=4)

def build_queries(files_to_run, prompt, overwrite: bool = False):
    queries = []
    metadata = []

    for file in files_to_run:
        with open(file, "r") as f:
            problem = json.load(f)
        
        if "attempts" not in problem:
            continue

        if len(problem["solutions"]) == 0:
            solution = "No ground truth solution provided."
        else:
            solution = problem["solutions"][0].get("solution", "No ground truth solution provided.")
        for i, attempt in enumerate(problem["attempts"]):
            if attempt.get("llm_judgment", None) is not None and not overwrite:
                continue

            query = prompt.format(
                problem=problem["problem"],
                ground_truth_solution=solution,
                proof_solution=attempt.get("solution", ""),
            )
            queries.append([
                {
                    "content": query,
                    "role": "user"
                }
            ])
            metadata.append({
                "attempt_index": i,
                "file": file
            })
    return queries, metadata
