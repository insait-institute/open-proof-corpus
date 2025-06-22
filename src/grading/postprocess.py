import json
import re
from collections import defaultdict
import random
random.seed(42)

def process_sample(file_name, judge_id):
    data = json.load(open(file_name, 'r'))

    data_list = []

    data_no_attempts = data.copy()
    del data_no_attempts["attempts"]

    for attempt in data["attempts"]:
        data_attempt = data_no_attempts.copy()
        if attempt["grading"] is None or attempt["grading"]["score"] is None:
            continue
        for key in attempt:
            data_attempt[key] = attempt[key]

        data_attempt["grading"]["judge_id"] = judge_id
        data_attempt["grading"] = [data_attempt["grading"]]
        data_list.append(data_attempt)
    
    return data_list

def exclude_basic(samples, exclude_regexes=[]):
    # Exclude samples based on basic criteria like "no_feedback" or "long"
    filtered_samples = []

    for sample in samples:
        if sample["grading"][0]["no_feedback"] or sample["grading"][0].get("long", False):
            continue
        to_exclude = False
        for exclude_regex in exclude_regexes:
            if re.match(exclude_regex, sample["problem_id"]):
                to_exclude = True
                break
        if not to_exclude:
            filtered_samples.append(sample)
    return filtered_samples

def join(samples):
    # join judgments
    joined_indices = []
    for i, sample in enumerate(samples):
        if i in joined_indices:
            continue
        for j in range(i + 1, len(samples)):
            second_sample = samples[j]
            if sample["problem_id"] == second_sample["problem_id"] and sample["model_id"] == second_sample["model_id"] and sample["solution"] == second_sample["solution"]:
                sample["grading"].extend(second_sample["grading"])
                joined_indices.append(j)
    
    # remove the joined samples
    samples = [sample for i, sample in enumerate(samples) if i not in joined_indices]
    return samples

def exclude_discrepancy(samples):
    # Exclude samples with discrepancies in grading
    filtered_samples = []
    for sample in samples:
        if len(sample["grading"]) == 1:
            filtered_samples.append(sample)
            continue
        
        scores = [g["score"] for g in sample["grading"]]
        if len(set(scores)) == 1:  # All scores are the same
            filtered_samples.append(sample)
    
    return filtered_samples

def train_test_split(samples, test_regexes=[]):
    # Split samples into train and test sets based on competitions
    train_samples = []
    test_samples = []

    for sample in samples:
        samples_same_questions = [
            s for s in samples if s["problem_id"] == sample["problem_id"]
        ]
        if any(re.match(test_regex, sample["problem_id"]) for test_regex in test_regexes) or all(len(s["grading"]) > 1 for s in samples_same_questions):
            test_samples.append(sample)
        else:
            train_samples.append(sample)
    
    return train_samples, test_samples


def random_train_test_split(samples, test_size=0.12, hold_out_model='deepseek/r1_0528'):
    # Split samples into train and test sets randomly
    hold_out_model_samples = []
    others_by_problem = defaultdict(list)

    for sample in samples:
        if sample['model_id'] == hold_out_model:
            hold_out_model_samples.append(sample)
        else:
            others_by_problem[sample['problem_id']].append(sample)

    # Get unique problem_ids and shuffle
    problem_ids = list(others_by_problem.keys())
    random.shuffle(problem_ids)

    # Compute number of test problems
    num_test = int(len(problem_ids) * test_size)
    test_problem_ids = set(problem_ids[:num_test])
    train_problem_ids = set(problem_ids[num_test:])

    # Split samples based on problem_id groups
    train_samples = [s for pid in train_problem_ids for s in others_by_problem[pid]]
    test_samples = [s for pid in test_problem_ids for s in others_by_problem[pid]]

    return train_samples, test_samples, hold_out_model_samples