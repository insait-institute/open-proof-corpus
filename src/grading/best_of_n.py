from .api import APIQuery
from .utils import extract_solution
from .ranking.tournament import SwissTournament, BracketTournament
from .ranking.judgment import Judgments, ModelAnswers
from concurrent.futures import ThreadPoolExecutor, as_completed
from .configs import load_config
from copy import deepcopy
from filelock import FileLock
import json
import random
import os
random.seed(42)

def get_all_model_ids(data):
    """
    Extract all model IDs from the data.
    """
    model_ids = set()
    for attempt in data.get("attempts", []):
        if "model_id" in attempt:
            model_ids.add(attempt["model_id"])
        if "other_selectors" in attempt:
            for other_attempt in attempt["other_selectors"]:
                if "model_id" in other_attempt:
                    model_ids.add(other_attempt["model_id"])
    return model_ids

def random_selector(project_config, solver_config, files_to_run, solver_config_judge_part):
    """
    Randomly select a file to run from the provided list.
    """
    for file in files_to_run:
        data = json.load(open(file, "r"))
        n_sols = len(data[solver_config.attempt_key])
        if n_sols > 0:
            if "attempts" not in data:
                data["attempts"] = []
            elif any(model_id.endswith(f" ({solver_config_judge_part['name']})") for model_id in get_all_model_ids(data)):
                continue
            random_index = random.randint(0, n_sols - 1)
            data["attempts"].append(data[solver_config.attempt_key][random_index].copy())
            data["attempts"][-1]["model_id"] = data["attempts"][-1]["model_id"] + f" ({solver_config_judge_part['name']})"
        
            with open(file, "w") as f:
                json.dump(data, f, indent=4)



def single(project_config, solver_config, files_to_run, solver_config_judge_part):
    queries = []
    file_data = dict()
    resolved_queries = dict()

    for file in files_to_run:
        data = json.load(open(file, "r"))
        if any(model_id.endswith(f" ({solver_config_judge_part['name']})") for model_id in get_all_model_ids(data)):
            continue
        file_data[file] = data
        for i, attempt in enumerate(data[solver_config.attempt_key]):
            query = [
                {
                    "role": "user",
                    "content": solver_config_judge_part["prompt"].format(problem=data["problem"], solution=attempt["solution"])
                }
            ]
            queries.append((file, i, query))
    
    config_judge = load_config(os.path.join(project_config.model_config_folder, solver_config_judge_part["judge"] + ".yaml"))

    del config_judge["human_readable_id"]
    if "date" in config_judge:
        del config_judge["date"]

    api_querier = APIQuery(
        **config_judge
    )

    for index, response, cost in api_querier.run_queries([q[2] for q in queries]):
        file, i, query = queries[index]
        data = file_data[file]
        if file not in resolved_queries:
            resolved_queries[file] = [None for _ in data[solver_config.attempt_key]]
        
        resolved_queries[file][i] = (response, cost)
        if not all(resolved_queries[file]):
            continue

        if "attempts" not in data:
            data["attempts"] = []

        total_cost = {
            "cost": sum(c["cost"] for _, c in resolved_queries[file]),
            "output_tokens": sum(c["output_tokens"] for _, c in resolved_queries[file]),
            "input_tokens": sum(c["input_tokens"] for _, c in resolved_queries[file]),
        }


        if solver_config_judge_part["mode"] == "discrete":
            correctness = [
                solver_config_judge_part["correct_word"] == extract_solution(response) for response, _ in resolved_queries[file]
            ]
            if not any(correctness):
                data["attempts"].append(data[solver_config.attempt_key][0].copy())
            else:
                correct_index = correctness.index(True)
                data["attempts"].append(data[solver_config.attempt_key][correct_index].copy())
        else:
            scores = [
                extract_solution(response, only_numeric=True) for response, _ in resolved_queries[file]
            ]
            for i, score in enumerate(scores):
                try:
                    float_score = float(score)
                except ValueError:
                    float_score = 0.0
                scores[i] = float_score
            data["attempts"].append(data[solver_config.attempt_key][scores.index(max(scores))].copy())

        data["attempts"][-1]["model_id"] = data["attempts"][-1]["model_id"] + f" ({solver_config_judge_part['name']})"
        cost_answers = {
            "cost": sum(c["cost"]["cost"] for c in data[solver_config.attempt_key]),
            "output_tokens": sum(c["cost"]["output_tokens"] for c in data[solver_config.attempt_key]),
            "input_tokens": sum(c["cost"]["input_tokens"] for c in data[solver_config.attempt_key]),
        }
        data["attempts"][-1]["cost"]["cost"] = cost_answers["cost"] + total_cost["cost"]
        data["attempts"][-1]["cost"]["output_tokens"] = cost_answers["output_tokens"] +  total_cost["output_tokens"]
        data["attempts"][-1]["cost"]["input_tokens"] = cost_answers["input_tokens"] +  total_cost["input_tokens"]
        data["attempts"][-1]["judge_data"] = resolved_queries[file]

        with open(file, "w") as f:
            json.dump(data, f, indent=4)


def dual(project_config,
         solver_config,
         files_to_run,
         solver_config_judge_part) -> None:

    # judge config is the same for every worker
    config_judge = os.path.join(
        project_config.model_config_folder,
        f"{solver_config_judge_part['judge']}.yaml",
    )

    # ---------- wrapped worker ---------- #
    def process_index(index: int) -> None:
        """
        Run the original body of the loop for *one* value of `index`.
        File writes stay thread-safe thanks to FileLock.
        """
        for file in files_to_run:

            # ───── quick pre-flight (no lock) ─────
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if any(
                model_id.endswith(f" ({solver_config_judge_part['name']})")
                for model_id in get_all_model_ids(data)
            ):
                continue                                         # already judged

            tournament_class = (
                SwissTournament
                if solver_config_judge_part["tournament_type"] == "swiss"
                else BracketTournament
            )

            # slice the candidate answers for *this* best-of-N round
            attempts_all     = data[solver_config.attempt_key]
            if solver_config_judge_part["same_judge"]:
                attempts_all = [
                    attempt
                    for attempt in attempts_all
                    if attempt["model_id"] == solver_config_judge_part["judge"]
                ]
            start, end       = index * solver_config.n_solutions, \
                               (index + 1) * solver_config.n_solutions
            attempts_slice   = attempts_all[start:end]

            # if fewer than n_solutions answers exist, skip
            if not attempts_slice:
                continue

            model_answers = ModelAnswers([a["solution"] for a in attempts_slice])
            judgments     = Judgments(model_answers)

            tournament = tournament_class(
                **solver_config_judge_part["tournament_config"],
                judge_prompt   = solver_config_judge_part["prompt"],
                model_config   = config_judge,
                judgments      = judgments,
                n_answers      = len(attempts_slice),
                problem_statement = data["problem"],
            )
            tournament.run_tournament(output_folder=None)
            ranking = tournament.get_ranking()
            best_ix = int(ranking.iloc[0]["answer"])

            # ───── critical section ─────
            lock = FileLock(f"{file}.lock")
            with lock:
                with open(file, "r", encoding="utf-8") as f:
                    data_locked = json.load(f)

                # duplicate-proof: another thread may have arrived first
                if any(
                    model_id.endswith(f" ({solver_config_judge_part['name']})")
                    for model_id in get_all_model_ids(data_locked)
                ):
                    return                                        # already written

                if "attempts" not in data_locked:
                    data_locked["attempts"] = []

                winner = deepcopy(attempts_slice[best_ix])

                # tag winner if judges differ
                if not solver_config_judge_part["same_judge"]:
                    winner["model_id"] += f" ({solver_config_judge_part['name']})"

                if solver_config.model_name_extension is not None:
                    winner["model_name_extension"] = solver_config.model_name_extension
                winner["judge_data"] = judgments.to_json()["judgments"]

                # aggregate cost (original slice + extra judging calls)
                extra_cost = {
                    "cost":          sum(j.cost["cost"]           for j in judgments.judgments),
                    "output_tokens": sum(j.cost["output_tokens"]  for j in judgments.judgments),
                    "input_tokens":  sum(j.cost["input_tokens"]   for j in judgments.judgments),
                }
                slice_cost = {
                    "cost":          sum(a["cost"]["cost"]           for a in attempts_slice),
                    "output_tokens": sum(a["cost"]["output_tokens"]  for a in attempts_slice),
                    "input_tokens":  sum(a["cost"]["input_tokens"]   for a in attempts_slice),
                }
                total_cost = winner["cost"].copy()
                total_cost["cost"]           = slice_cost["cost"]          + extra_cost["cost"]
                total_cost["output_tokens"]  = slice_cost["output_tokens"] + extra_cost["output_tokens"]
                total_cost["input_tokens"]   = slice_cost["input_tokens"]  + extra_cost["input_tokens"]
                winner["cost"] = total_cost
                winner["index"] = (start, end)

                data_locked["attempts"].append(winner)

                with open(file, "w", encoding="utf-8") as f:
                    json.dump(data_locked, f, indent=4)
        # end-for file
    # end process_index
    # ------------------------------------- #

    # Pick a sensible pool size; default to the exact n_best_of_n
    max_workers = getattr(solver_config, "max_parallel", solver_config.n_best_of_n)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(process_index, idx)
                   for idx in range(solver_config.n_best_of_n)]
        for f in as_completed(futures):
            f.result()   # propagate exceptions, if any