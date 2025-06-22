"""
best_of_n.py – generate N solutions per problem, score with a critic,
keep *all* generations/evals/rewards, and still record the best one.
"""

from pathlib import Path
from typing import List, Tuple

from vllm import LLM, SamplingParams
from transformers import AutoTokenizer
from verl.utils.reward_score.proof_reward import reward_continuous, reward_discrete
from datasets import load_dataset
import argparse

# ------------- CLI -------------

parser = argparse.ArgumentParser()
parser.add_argument("--critic", type=str,
                    default="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")
parser.add_argument("--critic-prompt", type=str,
                    default="runs/prompts/continuous_long.txt")
parser.add_argument("--dataset-path", type=str,
                    default="../data/best_of_n.jsonl")
parser.add_argument("--output-path", type=str,
                    default="../data/best_of_n.jsonl")
parser.add_argument("--continuous", action="store_true")
parser.add_argument("--temperature", type=float, default=0.6)
parser.add_argument("--top-p", type=float, default=0.95)
parser.add_argument("--batch-size", type=int, default=16)

args = parser.parse_args()

# ------------- Models & tokenizer -------------

critic_llm = LLM(model=args.critic, trust_remote_code=True)
tokenizer  = AutoTokenizer.from_pretrained(args.critic, trust_remote_code=True)

sampling_params_critic = SamplingParams(
    temperature=args.temperature,
    top_p=args.top_p,
    max_tokens=16000,
    n=1,
)

# ------------- Prompt templates -------------

critic_prompt_tmpl = Path(args.critic_prompt).read_text()

# ------------- Helper functions -------------

def build_chat(prompt: str) -> str:
    """Wrap raw prompt in the model’s native chat template."""
    return tokenizer.apply_chat_template(
        prompt, tokenize=False, add_generation_prompt=True
    )

def evaluate_solutions(
    problems: List[str],
    solutions: List[List[str]],
) -> Tuple[List[List[str]], List[List[float]]]:
    """
    Evaluate every (problem, solution) pair.
    Returns (nested evaluations, nested rewards) with the same shape as `solutions`.
    """
    critic_prompts, index_map = [], []      # keeps (problem_idx, solution_idx)

    for i, (p, sols) in enumerate(zip(problems, solutions)):
        for j, sol in enumerate(sols):
            if "</think>" in sol:
                # If the solution is already a thought process, we can use it directly
                sol = sol.split("</think>")[-1].strip()
            else:
                sol = f"Model answer is empty."
            critic_prompts.append(
                build_chat([
                    {
                        "role": "user",
                        "content": critic_prompt_tmpl.format(problem=p, solution=sol)
                    }
                ])
            )
            index_map.append((i, j))

    outs = critic_llm.generate(critic_prompts,
                               sampling_params=sampling_params_critic)
    flat_evals = [o.outputs[0].text.strip() for o in outs]

    # reshape into nested lists matching `solutions`
    evals  = [[] for _ in problems]
    rewards = [[] for _ in problems]

    for (i, j), ev in zip(index_map, flat_evals):
        rew = reward_continuous(ev) if args.continuous else reward_discrete(ev)
        evals[i].append(ev)
        rewards[i].append(rew)

    return evals, rewards

def process_batch(batch):
    problems = batch["problem"]            # list length = batch_size
    solutions = batch["solutions"]  # nested list
    evals, rews = evaluate_solutions(problems, solutions)

    # pick the best index *inside each problem’s list*
    best_indices     = [max(range(len(r)), key=r.__getitem__) for r in rews]
    best_solutions   = [s[idx] for s, idx in zip(solutions, best_indices)]
    best_evaluations = [e[idx] for e, idx in zip(evals, best_indices)]
    best_rewards     = [r[idx] for r, idx in zip(rews, best_indices)]

    return {
        "problem":          problems,
        "problem_id":      batch["problem_id"],  # keep the original ID
        "solutions":        solutions,
        "evaluations":      evals,
        "rewards":          rews,
        "best_solution":    best_solutions,
        "best_evaluation":  best_evaluations,
        "best_reward":      best_rewards,
    }

# ------------- Main -------------

def main():
    dataset = load_dataset("json", data_files=args.dataset_path, split="train")

    # map keeps the original order; we use a modest batch_size for GPU memory
    results = dataset.map(process_batch, batched=True, batch_size=args.batch_size)

    # save to JSONL – one line per *problem*
    results.to_json(args.output_path, orient="records", lines=True)

if __name__ == "__main__":
    main()