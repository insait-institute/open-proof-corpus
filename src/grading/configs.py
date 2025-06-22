from typing import Any, Dict, List
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, model_validator, ValidationError
import yaml


class JudgeConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')  # Disallow extra fields in the config
    id: str # Unique identifier for the judge
    name: str # Name of the judge
    undergraduate: Optional[bool] = False # Whether the judge can handle undergraduate problems

class JudgeLoadConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')  # Disallow extra fields in the config
    id: str # Unique identifier for the judge
    load: float # Load relative to other judges
    only_undergraduate: Optional[bool] = False # Whether to only add undergraduate problems for this judge
    problems: Optional[List[str]] = [] # List of problem regexes to assign to this judge
    only_duplicates: Optional[bool] = False # Whether to only assign problems that are duplicates of existing problems

class LLMJudgeConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')  # Disallow extra fields in the config
    prompt: str # Prompt to use for the LLM judge
    model: str # Model configuration to use for the LLM judge
    n_attempts: Optional[int] = 10 # Number of attempts to make for the LLM judge (if it fails because of out of tokens or similar)
    overwrite: Optional[bool] = False # Whether to overwrite existing solutions

class SolverConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')  # Disallow extra fields in the config
    prompt: str # Prompt to use for the solver
    prompt_gold: Optional[str] = None # Prompt to use for problems with a ground-truth solution
    type: Optional[str] = "default" # Type of solver, "default" or "best_of_n"
    attempt_key: Optional[str] = "attempts" # Key to store the attempts in. Should not be changed for default, and should be set to attempts_singular for best_of_n
    judges: Optional[List[dict]] = [] # List of LLM judges to use for the solver. Explanation of keys for this in README
    n_attempts: Optional[int] = 10 # Number of attempts to make for the solver (if it fails because of out of tokens or similar)
    problem_regexes: Optional[List[str]] = [".*"] # List of problem regexes to assign to this solver
    n_solutions: Optional[int] = 1 # Number of solutions to generate for each problem per model
    allow_shuffle: Optional[bool] = True  # Whether to allow shuffling of the solutions
    overwrite: Optional[bool] = False # Whether to overwrite existing solutions
    can_reject: Optional[bool] = True # Whether the solver can reject solutions
    earliest_date_added: Optional[str] = None # Earliest date added for the problems to be solved by this solver


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra='allow')  # Disallow extra fields in the config
    id: str # Unique identifier for the model
    human_readable_id: str # Human-readable identifier for the model
    date: Optional[str] = None # Date when the model was published, in YYYY-MM-DD format
    model: str # Model name, e.g. "gpt-3.5-turbo"
    api: str # API to use for the model, e.g. "openai" or "anthropic"
    temperature: Optional[float] = None # Temperature to use for the model, e.g. 0.7
    max_tokens: Optional[int] = None # Maximum number of tokens to generate for the model
    top_p: Optional[float] = None # Top-p to use for the model, e.g. 0.9
    read_cost: Optional[float] = 1 # Cost of reading a one million tokens for the model
    write_cost: Optional[float] = 1 # Cost of writing a one million tokens for the model

class DistributionConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')  # Disallow extra fields in the config
    n_problems: int # Number of problems to distribute
    overlap: float # Overlap between judges, as a percentage (0-1)
    competition_weight: Dict[str, float] # Weight of each competition, as a percentage (0-1)
    judge_file: str # Path to the judge file
    ignore_overlap: Optional[bool] = False # Whether to ignore the overlap between judges and just not assign problems dually.

class OverallConfig(BaseModel):
    # forbid unknown keys
    model_config = ConfigDict(extra='forbid')

    name: str # Name of the project
    slug: Optional[str] = "" # Slug for the project, not used atm
    admins: Optional[List[str]] = [] # List of admin judge IDs

    distribution_config: Optional[str] = None # Path to the distribution config file
    solver_config: Optional[str] = None # Path to the solver config file
    llm_judge_config: Optional[str] = None # Path to the LLM judge config file
    
    model_configs: Optional[List[str]] # List of paths to model config files
    problems_slug: Optional[str] = "Problem_Issues" # Slug for the problems, used to generate the folder name shown to admin judges
    solutions_slug: Optional[str] = "Solution_Issues" # Slug for the solutions, used to generate the folder name shown to admin judges
    discrepancies_slug: Optional[str] = "Discrepancies" # Slug for the discrepancies, used to generate the folder name shown to admin judges
    judged_base_folder: Optional[str] = None # Base folder for judged problems
    solved_base_folder: Optional[str] = None # Base folder for solved problems
    unsolved_base_folder: Optional[str] = None # Base folder for unsolved problems
    raw_base_folder: Optional[str] = None # Base folder for raw problems
    lock_base_folder: Optional[str] = None # Base folder for locks

    model_config_folder: Optional[str] = "configs/models" # Folder for model configs
    website_folder: Optional[str] = "website/data" # Folder for website data
    judge_file: Optional[str] = "configs/judges/judges.json" # Path to the judge file

    # run *before* the regular validation so we can patch the raw dict
    @model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, data: dict):
        """
        If the caller didn’t supply the three config paths,
        fill them with `{name}.yaml` or `{name}`.
        """
        name = data.get("slug")
        if name:                       # only if name is present
            data.setdefault("distribution_config", f"configs/distribution/{name}.yaml")
            data.setdefault("solver_config",       f"configs/solvers/{name}.yaml")
            data.setdefault("llm_judge_config",   f"configs/llm_graders/{name}.yaml")
            data.setdefault("judged_base_folder", f"data/judged/{name}")
            data.setdefault("solved_base_folder", f"data/solved/{name}")
            data.setdefault("unsolved_base_folder", f"data/unsolved/{name}")
            data.setdefault("raw_base_folder", f"data/raw/{name}")
            data.setdefault("lock_base_folder", f"data/locks/{name}")
        return data
    


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load a configuration file and return its content as a dictionary.
    """
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    for possible_config_class in [JudgeConfig, JudgeLoadConfig, SolverConfig, LLMJudgeConfig, DistributionConfig, OverallConfig, ModelConfig]:
        try:
            config = possible_config_class(**config)
            return config
        except ValidationError as e:
            continue
    return config