<div align="center">
  <h1>The Open Proof Corpus</h1>

  <a href="https://www.python.org/">
    <img alt="Build" src="https://img.shields.io/badge/Python-3.12-1f425f.svg?color=blue">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg">
  </a>
</div>

---

## 👋 Overview

This repository contains the code for the paper *The Open Proof Corpus: Building a Large-Scale, Human-Validated Dataset of LLM-Generated Proofs*. This README explains how to:

* Reproduce our experiments,
* Run your own experiment using our user interface,
* Train the model as described in the paper.

---

## 🚀 Installation

You can use either **UV** or **Conda** to install and manage dependencies.

### Option 1: Install Using UV

UV is a fast Python package manager.

* **macOS & Linux:**

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

* **Windows:**

  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

> If using UV, prepend all commands with `uv run`.

### Option 2: Using Conda

To use Conda:

```bash
conda create -n opc python=3.12
conda activate opc
python -m pip install -e .
```

This installs the project in editable mode.

---

## 🚧 Managing and Running Your Own Project

To use this codebase for your own project:

1. Own a website domain.
2. Use the `website` directory (a Flask app) to serve the UI.

We used **Nginx**, **pm2**, and `waitress-serve`, but other setups work too. To run locally:

```bash
cd website
pip install -e .
python main.py
```

This runs the user interface locally. You can now use the UI normally through your browser.

### Setting Up a Project

You need to define several config files. This repository already includes three fully-working example configurations that you can reference. See `src/grading/config.py` for all possible config options, we only mention the most important ones here.

#### `configs/projects/{project_name}.yaml`

```yaml
name: [[Name of the Project, can be anything]]
admins:
  - [[Judge ID of an admin. How to define a Judge ID is explained later]]
  - ...

model_configs:
  - [[Path to model config to run for this project, excluding yaml and relative to configs/models, e.g., openai/o3]]
  - ...
```

#### `configs/solvers/{project_name}.yaml`

```yaml
prompt: [[Prompts for questions. Will be formatted using problem={problem_statement}, so make sure that any loose brackets {,} appear doubled, and that "{problem}" appears somewhere in the prompt]]
prompt_gold: [[Prompt for questions that contain a final answer that can be extracted. Similar instructions as above.]]
n_solutions: [[Number of solutions to sample per model]]
problem_regexes:
  - [[Regex that has to match the problem path, defaults to everything. Multiple regexes will match the union of all them]]
  - ...
allow_shuffle: [[Whether to shuffle the model answers in each problem (good for anonymity), but can break if you run best-of-n selection and do not run the solver all at once ]]
overwrite: [[Whether to overwrite existing results]]
```

To setup a solver config for best-of-n selection, you additionally have to specify the following keys:

```yaml
type: "best_of_n"
attempt_key: "attempts_singular"

n_solutions: [[Number of solutions to select from ]]

judges:
  - name: [[Name of the judge]]
    judge: [[Config of the judge model, relative to configs/models]]
    mode: [[Either "random", "discrete", "continuous", or "dual"]]
    prompt: [[Prompt of the judge. Will be formatted with problem={problem_statement}, solution={model_solution} if the mode is not dual. If the mode is dual, then it will be formatted with problem={problem_statement}, solution_a={model_solution_a}, solution_b={model_solution_b}. Your prompt should state that the model should format its final answer in \boxed{{}}.]]
    correct_word: [[If mode=discrete, this will be used to compare the models judgment with to see if it thinks the proof is correct]]
    tournament_type: [[If mode=dual, the type of tournament that is run between model answers. Either "swiss" or "bracket"]]
    tournament_config: [[If mode=dual, the config of the tournament]]
      - max_losses: [[The maximum number of losses in a bracket tournament before a solution is finally removed.]]
      - n_rounds: [[Number of rounds in the swiss tournament]]
      - first_win_word: [[The word the model is instructed to output if the first output wins.]]
      - second_win_word: [[The word the model is instructed to output if the second output wins.]]
  - ...
```

#### `configs/distribution/{project_name}.yaml`

```yaml
n_problems: [[Number of problems to distribute to judges]]
overlap: [[Float between 0 and 1 indicating the frequency of problems that should be judged by two people.]]
judge_file: configs/judges/{project_name}.json
competition_weight:
 [[Competition name]]: [[Relative weight to other competitions]]
 ...
```

#### `configs/judges/{project_name}.json`

```json
"[Judge ID]": {
    "only_undergraduate": "[[Bool, indicating whether to only give undergraduate problems to this judge (false if empty)]]",
    "only_duplicates": "[[Bool, indicating whether to only give duplicate problems to this judge (false if empty)]]",
    "load": "[[Float, relative weight of number of problems to give to this judge compared to others]]"
},
```

#### `configs/llm_graders/{project_name}.yaml`

```yaml
prompt: [[Prompt to give to the LLM grader. Will be formatted with problem={problem}, ground_truth_solution={ground_truth_solution}, proof_solution={proof_solution}. The model should output its answer in valid JSON (shown below)]]
judge: [[Config of the judge model, relative to configs/models]]
overwrite: [[Whether to overwrite existing results]]
```

Required output format of an LLM judge:

```json
{
  "summary": "A concise summary of the proof solution.",
  "issues": [
    {
      "location": "A description of where the issue occurs in the proof",
      "text": "A citation or excerpt from the proof that contains the issue. If the issue is not contained to a very small part of the proof (e.g., a single sentence), you can leave this field empty.",
      "description": "A brief explanation of the issue.",
      "category": "The category of the issue (Overgeneralization, Oversimplification, Skipping Computation Steps, Citing Non-Standard Works or Theorems, Missing Edge Cases, Wrong Final Answer, Other)."
    }
  ]
}
```

---

## ➕ Adding a New Judge

1. Add a new Judge ID to `configs/judges/judges.json`. This file maps judge IDs to properties.
2. Add that ID to `configs/judges/{project_name}.json`.
3. If the judge is also an admin, add them to the admin list in `configs/projects/{project_name}.yaml`.

---

## ➕ Adding New Problems

1. Problems must be formatted as a list of dictionaries in `data/raw/{filename}.json`:

```json
{
  "problem_id": "[[Problem ID. Anything before the first '_' will be used as competition name]]",
  "metadata": {
    "[[Metadata key, can be anything]]": "[[Value]]",
    "level": "[[If undergraduate, will not be given to judges that cannot do this]]"
  },
  "problem": "[[Problem Statement]]",
  "solutions": [
    {
      "solution": "[[Ground Truth Solution]]",
      "images": {
        "[[key]]": "[[Link to image]]"
      },
      "[[Metadata key, can be anything]]": "[[Value]]"
    }
  ]
}
```

2. Then process and validate them:

```bash
python scripts/process.py --project {project_name} --file-name {filename}.json
python scripts/validate.py
```

Validation checks for consistency and uniqueness of paths.

---

## ▶️ Running New Problems

Once configs and API keys are in place, generate model outputs:

```bash
python scripts/solve.py --project {project_name}
```

## 🚚 Distributing Problems

Assign problems to judges for grading:

```bash
python scripts/distribution.py --project {project_name}
```

## ⟳ Recovering Problems

Fetch fully judged problems from the website:

```bash
python scripts/recover.py --project {project_name}
```

## ⏰ Monitoring Progress

Track judging progress and judge overlap:

```bash
python scripts/monitor.py --project {project_name}
```

## ✏️ Converting Results

Convert all raw results into a single export file:

```bash
python scripts/convert.py
```

## ➡️ Postprocessing Results

Prepare final results for use as training data:

```bash
python scripts/postprocess.py --project {project_name}
```

---

## 📊 Reproducing Results

Most results are directly included in the Open Proof Corpus. Extract them using:

```bash
notebooks/extraction.ipynb
```

---

## ⚖️ Evaluating LLM as a Judge

To evaluate the judging capabalities of a model on the test set after postprocessing, go through the following instructions:

### Obtaining judgments

Install additional libraries:

```bash
pip install -e .
pip install torch==2.6.0
pip install vllm==0.8.5
pip install flash_attn==2.7.4.post1
pip install flashinfer-python==0.2.2.post1
pip install -U ray==2.46.0
```

```bash
python scripts/judge_inference.py --judge_configs {judge_models} --setting_config discrete --n 5 --skip-existing
```

### Calculating results
To obtain the results, run:
```bash
python scripts/judge_results.py --setting_config discrete
```
## 🏋️‍♀️ Training a Verification Model

To finetune a verification model using the OPC, we adapt the `verl` framework, in which you should run the following steps:

### Preprocessing the data for training

To transform the data into a `parquet` format, as well as split the training data into training and validation, run:

```bash
python runs/preprocess.py --data_source ../data/{project_name}/train_samples.json --prompt_file runs/prompts/{prompt_file}
```

### Editing the verl configuration

You are free to change any hyperparameters in `runs/train.sh`, according to the [verl documentation](https://verl.readthedocs.io/en/latest/examples/config.html).

### Running the training script

To run the model, use the following command if you are running on a local server:

```bash
slurm/train.sbatch
```

or the following if you are using a Slurm cluster (overriding any of the default parameters if needed):

```bash
sbatch slurm/train.sbatch
```

The highest checkpoint according to the validation score is saved at `best_validation/`, while the latest checkpoints can be found in `checkpoints/`.

## 📄 Citation

```
@article{openproofcorpus2025,
  title={The Open Proof Corpus: A Large-Scale Human Study of LLM Proofs},
  author={Jasper Dekoninck and Ivo Petrov and  Kristian Minchev and Miroslav Marinov and Maria Drencheva and Lyuba Konova and Milen Milenov Shumanov and Kaloyan Tsvetkov and Nikolay Drenchev and Lazar D. Todorov and Kalina Nikolova and Nikolay Georgiev and Vanesa Kalinkova and Margulan Ismoldayev and Mislav Balunovic and Martin Vechev},
  journal={arXiv},
  year={2025},
}
```
