import os
import json
import sympy
from loguru import logger


from copy import deepcopy
from grading.api import APIQuery
from grading.verifier import Verifier
from grading.parser import WarningType, extract_judgement
from datasets import load_dataset
import numpy as np

def run(model_config, setting_config, config_path, skip_existing=False, output_folder="outputs"):
    model = model_config["model"]
    n = model_config["n"]
    api = model_config["api"]


    max_tokens = model_config.get("max_tokens", setting_config["default_max_tokens"])
    temperature = model_config.get("temperature", setting_config["default_temperature"])
    kwargs = model_config.copy()
    del kwargs["model"]
    del kwargs["n"]
    del kwargs["api"]
    del kwargs["human_readable_id"]
    if 'date' in kwargs:
        del kwargs['date']
    kwargs["max_tokens"] = max_tokens
    kwargs["temperature"] = temperature
    
    logger.info(f"New run, model: {model}, competition: {setting_config['name']}")

    if os.path.exists(setting_config["data_path"]):
        with open(setting_config['data_path'], 'r') as f:
            problems = json.load(f)
            if setting_config.get('n_solutions', -1) != -1:
                problems = problems[:setting_config.get('n_solutions', -1)]
    else:
        logger.info(f"Loading dataset from {setting_config['data_path']}")
        problems = load_dataset(setting_config['data_path'], split='test')
        problems = problems.to_list()
        if setting_config.get('n_solutions', -1) != -1:
            problems = problems[:setting_config.get('n_solutions', -1)]

    output_dir = os.path.join(output_folder, setting_config['name'])
    os.makedirs(output_dir, exist_ok=True)

    batch_prompts = []
    batch_idx_to_problem_idx = {}

    all_grades_per_problem = {i: [] for i in range(len(problems))}
    detailed_costs_per_problem = {i: [] for i in range(len(problems))}

    for i, problem in enumerate(problems):
        problem_id = problem["problem_id"].replace('/', '_')
        model_id = problem['model_id']
        output_file = os.path.join(output_dir, config_path, model_id, f"{problem_id}.json")
        if skip_existing and os.path.exists(output_file):
            data_file = json.load(open(output_file))
            existing_grades = data_file["messages"]
            
            # print all the message lengths
            if "detailed_costs" in data_file:
                detailed_costs = data_file["detailed_costs"]
            else:
                cost = data_file["cost"]
                detailed_costs = [{"cost": cost["cost"] if i == 0 else 0, 
                                    "input_tokens": cost["input_tokens"] if i == 0 else 0, 
                                    "output_tokens": cost["output_tokens"] if i == 0 else 0} 
                                    for i in range(len(existing_grades))]
                
            detailed_costs_per_problem[i] = detailed_costs
            all_grades_per_problem[i] = existing_grades
            logger.info(f"Skipping problem: {problem_id} ({len(existing_grades)} times)")
            if len(existing_grades) == n:
                calculate_problem_results(model_config, config_path, problem, output_dir, existing_grades,
                                        detailed_costs, model, setting_config['discrete'])
                continue

        for _ in range(n - len(all_grades_per_problem[i])):
            batch_idx_to_problem_idx[len(batch_prompts)] = i
            batch_prompts.append(problem)

    if len(batch_prompts) == 0:
        return
    
    logger.info("Collected all queries, now running")
    if api != 'baseline':
        api = APIQuery(
            model=model, 
            api=api,
            **kwargs
        )

    with open(setting_config['prompt_path'], 'r') as f:
        prompt_template = f.read()
    if api != 'baseline':
        verifier = Verifier(
            querier=api,
            system_prompt=setting_config.get('system_prompt', None),
            prompt_template=prompt_template
        )
    else:
        verifier = Verifier(
            discrete=setting_config['discrete'],
            **kwargs
        )

    for idx, messages, detailed_cost in verifier.verify(batch_prompts):
        problem_idx = batch_idx_to_problem_idx[idx]
        problem = problems[problem_idx]
        all_grades_per_problem[problem_idx].append(messages)
        detailed_costs_per_problem[problem_idx].append(detailed_cost)

        # check if the whole problem is finished
        if len(all_grades_per_problem[problem_idx]) == n:
            calculate_problem_results(model_config, config_path, problem, output_dir, 
                                      all_grades_per_problem[problem_idx], 
                                      detailed_costs_per_problem[problem_idx], 
                                      model, setting_config['discrete'])
    if api != 'baseline':
        api.free_model()


def calculate_problem_results(model_config, config_path, problem, output_dir, messages_problem, 
                              costs_problem, verifier_id, is_binary_text):
    problem_id = problem["problem_id"].replace('/', '_')
    model_id = problem['model_id']
    output_file = os.path.join(output_dir, config_path, model_id, f"{problem_id}.json")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    n = len(messages_problem)
    judgements = []
    warnings = []
    corrects = []
    try:
        gold_judgement = 0 if any([grading['score'] == 0 for grading in problem['grading']]) else 1
    except:
        gold_judgement = 1 if all(problem["score"]) else 0
    for j in range(n):
        model_answer = messages_problem[j][-1]['content']
        model_judgement, warning = extract_judgement(model_answer, gold_judgement, is_binary_text=is_binary_text)
        if is_binary_text:
            is_correct = model_judgement == gold_judgement
        else:
            is_correct = model_judgement
        if len(model_answer) == 0:
            logger.warning(f"Empty message in problem: {problem_id}, idx: {j}")
            warning = WarningType.MAJOR
        judgements.append(model_judgement)
        warnings.append(warning.value)
        corrects.append(is_correct)
        try:
            grading_data = deepcopy(problem['grading'][0])
        except:
            grading_data = {
                "details": [{
                    "score": 0,
                    "feedback": "",
                    "judge_id": verifier_id
                }],
            }
        grading_data['details'][0]['score'] = model_judgement
        grading_data['details'][0]['feedback'] = model_answer
        grading_data['score'] = model_judgement
        grading_data['judge_id'] = verifier_id

    try:
        logger.info(f"Finished problem {problem_id}, solved by {model_id} - judgements: {judgements}, gold answer: {gold_judgement}, #Correct: {sum(corrects)}")
    except:
        pass

    pass_at_1 = sum(corrects)/n
    if is_binary_text:
        if n%2 == 0 and sum(corrects) == n//2:
            logger.warning(f"Even number of samples have a 50/50 split of judgements, defaulting to incorrect.")
            majority_vote = 0
        elif sum(corrects) < n/2:
            majority_vote = 1 - gold_judgement
        else:
            majority_vote = gold_judgement
        
        maj_at_n = majority_vote == gold_judgement
    else:
        maj_at_n = np.mean(corrects)
        majority_vote = np.mean(corrects)

    for i in range(len(costs_problem)):
        costs_problem[i]["cost"] = model_config["read_cost"] * costs_problem[i]["input_tokens"] + model_config["write_cost"] * costs_problem[i]["output_tokens"]
        costs_problem[i]["cost"] /= 10 ** 6
    cost = {
        "cost": sum([d["cost"] for d in costs_problem]),
        "input_tokens": sum([d["input_tokens"] for d in costs_problem]),
        "output_tokens": sum([d["output_tokens"] for d in costs_problem]),
    }
    
    with open(output_file, "w") as f:
        json.dump({
                    "metadata": problem.get("metadata", {}),
                    "problem": problem['problem'],
                    "problem_id": problem_id,
                    "solutions": problem['solutions'],
                    "grading_scheme": problem['grading_scheme'],
                    "model_id": model_id,
                    "cost": cost,
                    "gold_judgement": gold_judgement,
                    "original_judges": [grading['judge_id'] for grading in problem['grading']],
                    "types": problem.get("metadata", {}).get("problem_types", "None"),
                    "grading": grading_data, 
                    "judgements": judgements,
                    "correct": corrects,
                    "pass_at_1": pass_at_1,
                    "majority_vote": majority_vote,
                    "maj_at_n": maj_at_n,
                    "cost": cost,
                    "detailed_costs": costs_problem,
                    "warnings": warnings,
                    "messages": messages_problem,
                    'had_llm': 'llm_judgment' in problem
                }, f)

def convert_answer(answer):
    try:
        if type(answer) == sympy.Integer:
            return int(answer)
        else:
            return str(answer)
    except:
        return "None"