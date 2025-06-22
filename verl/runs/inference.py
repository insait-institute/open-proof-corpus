from datasets import load_dataset
import argparse
from vllm import LLM, SamplingParams
from transformers import AutoTokenizer


parser = argparse.ArgumentParser()
parser.add_argument("--model", type=str, default="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")
parser.add_argument("--temperature", type=float, default=0.6)
parser.add_argument("--top-p", type=float, default=0.95)
parser.add_argument("--max-tokens", type=int, default=16000)
parser.add_argument("--batch-size", type=int, default=16)
parser.add_argument("--n", type=int, default=8)
parser.add_argument("--dataset-path", type=str, default="../data/train/discrete/simple/train.parquet")
parser.add_argument("--output-path", type=str, default="../data/train/discrete/simple/inference_results.jsonl")

args = parser.parse_args()


dataset = load_dataset("parquet", data_files=args.dataset_path, split="train")

# sample 10 samples for testing

llm = LLM(model=args.model, trust_remote_code=True)

tokenizer = AutoTokenizer.from_pretrained(args.model,
                                          trust_remote_code=True)

sampling_params = SamplingParams(
    temperature=args.temperature,
    top_p=args.top_p,
    max_tokens=args.max_tokens,
    n=args.n,
)

def generate_responses(batch):
    # build chat messages for every row
    prompts = []
    for question in batch["prompt"]:
        # turn list-of-dicts → single string prompt
        prompt = tokenizer.apply_chat_template(
            question,
            tokenize=False,            # we want raw text here
            add_generation_prompt=True # adds the <assistant> tag, etc.
        )
        prompts.append(prompt)
    
    outs = llm.generate(prompts, sampling_params=sampling_params)

    # For each prompt collect every completion the model produced
    responses = [
        [gen.text for gen in out.outputs]   # len(out.outputs) == n
        for out in outs
    ]

    return {"responses": responses}         # note the plural!


results = dataset.map(generate_responses, batched=True,
                      batch_size=args.batch_size)
results.to_json(args.output_path, orient="records", lines=True)