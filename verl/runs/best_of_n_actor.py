"""
best_of_n.py – generate N solutions per problem, score with a critic,
keep *all* generations/evals/rewards, and still record the best one.
"""

from pathlib import Path
from typing import List, Tuple

from vllm import LLM, SamplingParams
from transformers import AutoTokenizer
from datasets import load_dataset
import argparse

# ------------- CLI -------------

parser = argparse.ArgumentParser()
parser.add_argument("--actor", type=str,
                    default="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")
parser.add_argument("--actor-prompt", type=str,
                    default="runs/prompts/solve.txt")
parser.add_argument("--dataset-path", type=str,
                    default="../data/test_samples.json")
parser.add_argument("--output-path", type=str,
                    default="../data/best_of_n.jsonl")
parser.add_argument("--n", type=int, default=8)
parser.add_argument("--temperature", type=float, default=0.6)
parser.add_argument("--top-p", type=float, default=0.95)
parser.add_argument("--batch-size", type=int, default=8)
args = parser.parse_args()

# ------------- Models & tokenizer -------------

actor_llm  = LLM(model=args.actor,  trust_remote_code=True)
tokenizer  = AutoTokenizer.from_pretrained(args.actor, trust_remote_code=True)

sampling_params_actor = SamplingParams(
    temperature=args.temperature,
    top_p=args.top_p,
    max_tokens=32000,
    n=args.n,
)

# ------------- Prompt templates -------------

actor_prompt_tmpl  = Path(args.actor_prompt).read_text()

# ------------- Helper functions -------------

def build_chat(prompt: str) -> str:
    """Wrap raw prompt in the model’s native chat template."""
    return tokenizer.apply_chat_template(
        prompt, tokenize=False, add_generation_prompt=True
    )

def generate_solutions(problems: List[str]) -> List[List[str]]:
    """Return [[sol1, …, sol_n] for each problem]."""
    prompts = [build_chat([
        {
            "role": "user",
            "content": actor_prompt_tmpl.format(problem=p)
        }
    ]) for p in problems]
    outs = actor_llm.generate(prompts, sampling_params=sampling_params_actor)
    return [[g.text.strip() for g in out.outputs] for out in outs]


def process_batch(batch):
    problems = batch["problem"]            # list length = batch_size
    sols = generate_solutions(problems)    # nested list
    return {
        "problem":          problems,
        "problem_id":      batch["problem_id"],  # keep the original ID
        "solutions":        sols,
    }

# ------------- Main -------------

def main():
    dataset = load_dataset("json", data_files=args.dataset_path, split="train")
    # select only first 10 samples for testing
    dataset = dataset.select(range(10))  # uncomment for testing

    # map keeps the original order; we use a modest batch_size for GPU memory
    results = dataset.map(process_batch, batched=True, batch_size=args.batch_size)

    # save to JSONL – one line per *problem*
    results.to_json(args.output_path, orient="records", lines=True)

if __name__ == "__main__":
    main()