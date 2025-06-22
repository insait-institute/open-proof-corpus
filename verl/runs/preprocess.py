import argparse
import os
import re
import json

import datasets
import random
from datetime import datetime

from verl.utils.hdfs_io import copy, makedirs

random.seed(42)

def extract_solution(text):
    pattern = r'\\boxed{([^}]*)}'
    matches = re.findall(pattern, text)

    if matches:
        return matches[-1].lower()
    else:
        return "none"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-dir", default="../data/train")
    parser.add_argument("--data-source", default="../data/train_samples.json")
    parser.add_argument("--prompt-file", default="runs/prompts/discrete_simple.txt")
    parser.add_argument("--train-size", type=float, default=0.8)

    args = parser.parse_args()

    dataset = json.load(open(args.data_source, "r"))

    random.shuffle(dataset)
    problem_ids = list(set([el["problem_id"] for el in dataset]))
    train_problem_ids = problem_ids[:int(len(problem_ids) * args.train_size)]
    test_problem_ids = problem_ids[int(len(problem_ids) * args.train_size):]

    dataset = {
        "train": [el for el in dataset if el["problem_id"] in train_problem_ids],
        "test": [el for el in dataset if el["problem_id"] in test_problem_ids],
    }

    train_dataset = datasets.Dataset.from_list(dataset["train"])
    test_dataset = datasets.Dataset.from_list(dataset["test"])

    instruction_following = open(args.prompt_file, "r").read().strip()

    # add a row to each data item that represents a unique id
    def make_map_fn(split):
        def process_fn(example, idx):
            problem = example.pop("problem")
            model_solution = example.pop("solution")
            for sol in example['solutions']:
                if not sol['images']:
                    sol['images'] = {'dummy': ''}
            question = instruction_following.format(problem=problem, solution=model_solution)

            correctness = example.pop("grading")
            correctness = correctness[0]["score"]

            data = {
                "data_source": args.data_source,
                "prompt": [
                    {
                        "role": "user",
                        "content": question,
                    }
                ],
                "ability": "math",
                "reward_model": {"style": "rule", "ground_truth": "correct" if correctness == 1 else "incorrect"},
                "extra_info": {
                    "split": split,
                    "index": idx,
                    "time": datetime.now().isoformat(),
                },
            }
            return data

        return process_fn

    train_dataset = train_dataset.map(function=make_map_fn("train"), with_indices=True)
    test_dataset = test_dataset.map(function=make_map_fn("test"), with_indices=True)

    # print a single instance of the train dataset
    print(train_dataset[0]["prompt"][0]["content"])

    local_dir = args.save_dir
    train_dataset.to_parquet(os.path.join(local_dir, "train.parquet"))
    test_dataset.to_parquet(os.path.join(local_dir, "test.parquet"))
