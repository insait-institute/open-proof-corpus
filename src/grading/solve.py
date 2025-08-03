from .api import APIQuery
from .parser import parse_answer, extract_answer, check_answers
from concurrent.futures import ThreadPoolExecutor, as_completed
from .configs import *

import os
import glob
import re
import json
from datetime import datetime
import random
from filelock import FileLock, Timeout
from loguru import logger
from .proofagent import ProofAgent

def solve_agent(project_config, solver_config, files_to_run, config_name):
    futures = []
    total_cost = 0
    solutions_to_generate = solver_config.n_solutions

    with ThreadPoolExecutor(max_workers=16) as pool:
        for sol_index in range(solutions_to_generate):
            cfg = load_config(os.path.join(project_config.model_config_folder, config_name + ".yaml"))
            del cfg["human_readable_id"]
            if "date" in cfg:
                del cfg["date"]
            
            futures.append(pool.submit(
                single_loop_agent, solver_config, project_config,
                files_to_run, config_name, sol_index, cfg
            ))
        total_cost = sum(f.result() for f in as_completed(futures))

    return total_cost

def single_loop_agent(solver_config, project_config, files_to_run, config_name, sol_index=0, config=None):
    total_cost = 0
    problems_to_run = generate_problems_to_run(solver_config, project_config, files_to_run, 
                                               config_name, sol_index, 0)
    files_to_run = [p[0] for p in problems_to_run]
    for file_to_run in files_to_run:
        data = json.load(open(file_to_run, "r"))
        file_solved = file_to_run.replace(project_config.unsolved_base_folder, project_config.solved_base_folder)
        if os.path.exists(file_solved) and (not solver_config.overwrite):
            data_solved = json.load(open(file_solved, "r"))
            if sol_index in [attempt.get("sol_index", sol_index) 
                             for attempt in data_solved[solver_config.attempt_key] if attempt["model_id"] == config_name]:
                logger.info(f"Already solved {file_to_run} with {config_name}")
                continue
        
        model_config = load_config(os.path.join(project_config.model_config_folder, config_name + ".yaml"))
        if "date" in model_config:
            del model_config["date"]
        if "human_readable_id" in model_config:
            del model_config["human_readable_id"]
        querier = APIQuery(
            **model_config
        )
        agent = ProofAgent(querier, solver_config.prompts, return_if_not_found=solver_config.return_if_not_found)
        solution, cost = agent.agent(data['problem'])
        total_cost += cost['cost']

        if solution is None:
            solution = ""
            logger.warning(f"Failed to solve {file_to_run} with {config_name}")
            return 0

        save_file(data, solver_config, project_config, config_name, 30, 0, 
                  solution, cost, file_to_run, False, None, sol_index)
    return 0


def solve(project_config : OverallConfig, solver_config : SolverConfig, 
          files_to_run : List[str], config_name : str, timeout: int = 30):
    futures = []
    total_cost = 0
    solutions_to_generate = solver_config.n_solutions
    if solver_config.n_best_of_n is not None:
        solutions_to_generate *= solver_config.n_best_of_n

    with ThreadPoolExecutor(max_workers=16) as pool:
        for sol_index in range(solutions_to_generate):
            cfg = load_config(os.path.join(project_config.model_config_folder, config_name + ".yaml"))
            del cfg["human_readable_id"]
            if "date" in cfg:
                del cfg["date"]
            
            futures.append(pool.submit(
                single_loop, solver_config, project_config,
                files_to_run, config_name, timeout, sol_index, cfg
            ))
        total_cost = sum(f.result() for f in as_completed(futures))
    return total_cost

def reject_result(result, cost, gold_answer=None):
    if result is None or len(result) == 0:
        return True
    if cost["output_tokens"] > 30000:
        # check if it is a power of 2
        if cost["output_tokens"] & (cost["output_tokens"] - 1) == 0:
            return True
        if cost["output_tokens"] % 1000 == 0:
            return True
    if gold_answer is not None:
        parsed_gold_answer = parse_answer(gold_answer)[0]
        extracted_answer = extract_answer(result)[0]
        if not check_answers(parsed_gold_answer, extracted_answer):
            return True
    return False

def single_loop(solver_config : SolverConfig, project_config : OverallConfig,
                files_to_run : List[str], config_name : str, timeout: int = 30, 
                sol_index: int = 0, config: dict = None):
    total_cost = 0
    for i in range(solver_config.n_attempts):
        problems_to_run = generate_problems_to_run(solver_config, project_config, files_to_run, config_name, sol_index, i)
        
        if len(problems_to_run) == 0:
            if i == 0:
                logger.info(f"No problems to run for {config_name}")
            continue

        querier = APIQuery(
            **config
        )

        total_cost += run_problem(solver_config, project_config, config_name, timeout, 
                                  i, problems_to_run, querier, sol_index)
    logger.info(f"Total cost for {config_name}: {total_cost}")
    return total_cost

def run_problem(solver_config, project_config, config_name, timeout, i, problems_to_run, querier, sol_index):
    total_cost = 0
    for idx, result, cost in querier.run_queries([p[1] for p in problems_to_run]):
        total_cost += cost["cost"]
        if idx % 10 == 0:
            logger.info(f"Processed {idx} problems with {config_name}, total cost: {total_cost}")
        if "</think>" in result:
            think_result = result.split("</think>")[0]
            result = result.split("</think>")[-1]
        else:
            think_result = None
        problem_path = problems_to_run[idx][0]
        data        = json.load(open(problem_path, "r"))
        rejected = False
        grading = None
        if solver_config.can_reject and reject_result(result, cost, data.get("gold_answer")):
            logger.info(f"Rejected result for {problem_path} with {config_name}")
            if i == solver_config.n_attempts - 1:
                result = f"The model was unable to solve this problem. After {solver_config.n_attempts} attempts, each solution was either incorrect, hit the token limit (64000), or was empty."
                rejected = True
                grading = {
                        "details": [
                            {
                                "part_id": 1,
                                "score": 0,
                                "feedback": "The model was unable to solve this problem. Therefore, the solution is automatically graded as incorrect."
                            }
                        ],
                        "score": 0,
                        "uncertain": False,
                        "no_feedback": False,
                        "long": False,
                        "auto_grade": True,
                    }
            else:
                continue

        save_file(data, solver_config, project_config, config_name, timeout, i, 
                  result, cost, problem_path, rejected, grading, sol_index, think_result)
    return total_cost

def save_file(data, solver_config, project_config, config_name, timeout, i, 
              result, cost, problem_path, rejected, grading, sol_index, think_result=None):
    file_solved = problem_path.replace(project_config.unsolved_base_folder, project_config.solved_base_folder)
    file_lock_path = problem_path.replace(project_config.unsolved_base_folder, project_config.lock_base_folder)
    os.makedirs(os.path.dirname(file_solved), exist_ok=True)
    os.makedirs(os.path.dirname(file_lock_path), exist_ok=True)

            # --------- begin critical section ---------
    lock = FileLock(file_lock_path + ".lock", unlink_on_release=True)      # one lock per JSON file
    try:
        with lock.acquire(timeout=timeout):
                    # 1) read the current contents (if any)
            if (os.path.exists(file_solved) and (not solver_config.overwrite or i > 0)):
                with open(file_solved, "r") as fh:
                    data = json.load(fh)
            else:
                data[solver_config.attempt_key] = []

                    # 2) update in memory
            data[solver_config.attempt_key].append(
                        {
                            "model_id":  config_name,
                            "model_name_extension": solver_config.model_name_extension,
                            "solution":  result,
                            "thinking": think_result,
                            "cost":      cost,
                            "grading":   grading,
                            "rejected": rejected,
                            "annotations": None,
                            "sol_index": sol_index,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
            if solver_config.allow_shuffle:
                random.shuffle(data[solver_config.attempt_key])
                    # put all rejected attempts at the end
            data[solver_config.attempt_key] = sorted(data[solver_config.attempt_key], key=lambda x: x.get("rejected", False))

                    # 3) **atomic write**: write to a tmp file, then replace
            tmp = file_solved + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(data, fh, indent=4)
            os.replace(tmp, file_solved)        # atomic on POSIX & Windows
    except Timeout:
        logger.warning(f"Could not obtain lock on {file_solved} within {timeout}s")

def generate_problems_to_run(solver_config, project_config, files_to_run, config_name, sol_index, i):
    problems_to_run = []
    for file in files_to_run:
        data = json.load(open(file, "r"))
        file_solved = file.replace(project_config.unsolved_base_folder, project_config.solved_base_folder)
        if os.path.exists(file_solved) and (not solver_config.overwrite or i > 0):
            data_solved = json.load(open(file_solved, "r"))
            if sol_index in [attempt.get("sol_index", sol_index) 
                             for attempt in data_solved[solver_config.attempt_key] if attempt["model_id"] == config_name]:
                if i == 0:
                    logger.info(f"Already solved {file} with {config_name}")
                continue
        if data.get("gold_answer"):
            problems_to_run.append((file, [
                    {
                        "role": "user",
                        "content": solver_config.prompt_gold.format(problem=data["problem"])
                    }
                ]))
        elif solver_config.prompt is not None:
            problems_to_run.append((file, [
                    {
                        "role": "user",
                        "content": solver_config.prompt.format(problem=data["problem"])
                    }
                ]))
        else:
            problems_to_run.append((file, [
                    {
                        "role": "user",
                        "content": data["problem"]
                    }
                ]))
    return problems_to_run