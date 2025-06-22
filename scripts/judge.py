from grading.configs import load_config
from grading.judge import judge
import os
import glob
import argparse
import re


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Solve problems using the API.")
    parser.add_argument("--project")
    parser.add_argument("--config-base", default="configs/projects")

    args = parser.parse_args()

    project_config = load_config(os.path.join(args.config_base, args.project + ".yaml"))

    solver_config = load_config(project_config.llm_judge_config)

    all_problem_files = glob.glob(f"{project_config.solved_base_folder}/**/*.json", recursive=True)

    judge(
        project_config,
        solver_config,
        all_problem_files,
    )
    