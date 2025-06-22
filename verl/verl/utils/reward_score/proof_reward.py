import re
import numpy as np

def extract_solution(text: str) -> str:
    start_tag = r'\boxed{'
    start = text.rfind(start_tag)
    if start == -1:
        return "none"

    i = start + len(start_tag)
    depth = 1
    while i < len(text) and depth:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1

    if depth:                       # never balanced → abort
        return "none"

    sol = text[start + len(start_tag) : i - 1]  # slice inside the braces

    while True:
        new_sol = re.sub(r'\\text\s*\{([^{}]*)\}', r'\1', sol)
        if new_sol == sol:          # nothing left to unwrap
            break
        sol = new_sol

    sol = re.sub(r'\s+', '', sol).lower()
    return sol

def reward_discrete(solution_str):
    return 1 if extract_solution(solution_str) == "correct" else 0

def proof_reward(data_source, solution_str, ground_truth, extra_info):
    return extract_solution(solution_str) == ground_truth.lower()

def reward_continuous(solution_str):
    extracted_solution = extract_solution(solution_str)
    if extracted_solution == "none":
        return "none"
    if "%" in extracted_solution:
        extracted_solution = extracted_solution.replace("%", "")
    # remove any non-numeric characters except for the decimal point
    extracted_solution = re.sub(r'[^\d.]', '', extracted_solution)
    if extracted_solution == "." or extracted_solution.count('.') > 1:
        extracted_solution = None
    extracted_solution = float(extracted_solution) if extracted_solution else None
    if extracted_solution is None:
        extracted_solution = 50
    if extracted_solution > 1:
        extracted_solution /= 100
    if extracted_solution < 0:
        extracted_solution = 0
    if extracted_solution > 1:
        extracted_solution = 1
    return extracted_solution

def proof_reward_continuous(data_source, solution_str, ground_truth, extra_info):
    extracted_solution = reward_continuous(solution_str)

    if extracted_solution == "none":
        return np.log(0.01)

    if ground_truth == "correct":
        return np.log(max(0.01, extracted_solution))
    elif ground_truth == "incorrect":
        return np.log(max(0.01, 1 - extracted_solution))
    else:
        return np.log(0.01)

    
