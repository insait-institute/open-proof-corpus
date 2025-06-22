import os
import json
import argparse
import glob
from grading.configs import load_config
from grading.recover import recover



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recover problems from the API.")
    parser.add_argument("--project", help="Project name to recover.")
    parser.add_argument("--config-base", default="configs/projects")
    parser.add_argument("--remove", action="store_true", help="Remove existing files before recovering.")

    args = parser.parse_args()

    project_config = load_config(os.path.join(args.config_base, args.project + ".yaml"))

    recover(project_config, args.remove)
