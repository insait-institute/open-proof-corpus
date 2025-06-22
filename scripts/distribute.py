import argparse
import random

from grading.distribute import distribute
from grading.configs import load_config
import os

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
random.seed(42)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distribute problems to different folders.")

    parser.add_argument("--project", help="Name of the config file to use.")
    parser.add_argument("--config-base", default="configs/projects", help="Base folder for the config files.")
    parser.add_argument("--only-admin", action="store_true", help="Only distribute admin problems.")

    args = parser.parse_args()

    project_config = load_config(os.path.join(args.config_base, f"{args.project}.yaml"))
    config = load_config(project_config.distribution_config)

    distribute(project_config, config, args.only_admin)
