from vllm import LLM, SamplingParams
from transformers import AutoTokenizer
from verl.utils.reward_score.proof_reward import reward_discrete, reward_continuous

llms_proof_reward = dict()

def compute_score(data_sources, solution_strs, ground_truths, extra_infos):
    """
    Compute scores for a batch of data. Using a proof evaluator
    """
    pass
    extra_info = extra_infos[0] # for now, assume all extra_infos are the same for our purpose, except for the question
    prompt = extra_info["prompt"]
    temperature = extra_info.get("temperature", 0.6)
    top_p = extra_info.get("top_p", 0.95)
    max_tokens = extra_info.get("max_tokens", 16000)
    batch_size = extra_info.get("batch_size", 16)
    llm = extra_info.get("model_name", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B")

    if llm not in llms_proof_reward:
        gpu_memory_utilization = extra_info.get("gpu_memory_utilization", 0.3) # Lets hope no OOM error
        llms_proof_reward[llm] = {
            "model": LLM(model=llm, trust_remote_code=True, gpu_memory_utilization=gpu_memory_utilization),
            "tokenizer": AutoTokenizer.from_pretrained(llm, trust_remote_code=True),
        }

    sampling_params = SamplingParams(
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        n=1,  # For proof reward, we only need one response
    )
    llm_model = llms_proof_reward[llm]["model"]
    tokenizer = llms_proof_reward[llm]["tokenizer"]
    processed_solutions = []
    for solution in solution_strs:
        if "</think>" in solution:
            # If the solution is already a thought process, we can use it directly
            processed_solutions.append(solution.split("</think>")[-1].strip())
        else:
            processed_solutions.append(f"Model answer is empty.")

    prompts = []

    for extra_info_here, solution in zip(extra_infos, processed_solutions):
        prompt_here = prompt.format(problem=extra_info_here["question"], solution=solution)
        prompt_here = tokenizer.apply_chat_template(
            prompt_here,
            tokenize=False,  # we want raw text here
            add_generation_prompt=True  # adds the <assistant> tag, etc.
        )
        prompts.append(prompt_here)
    
    outs = llm_model.generate(prompts, sampling_params=sampling_params)
    scores = []
    for out, ground_truth in zip(outs, ground_truths):
        response = out.outputs[0].text.strip()
        if extra_info["continuous"]:
            score = reward_continuous(response, ground_truth)
        else:
            score = reward_discrete(response, ground_truth)
        scores.append(score)
    
    return scores