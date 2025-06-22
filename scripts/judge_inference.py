import argparse
from grading.runner import run
import yaml
import sys
from loguru import logger

sys.path.append('../')

parser = argparse.ArgumentParser()
parser.add_argument("--n", type=int, default=5)
parser.add_argument("--judge_configs", type=str, nargs='+', required=True)
parser.add_argument("--setting_config", type=str, required=True)
parser.add_argument("--skip-existing", action="store_true")
parser.add_argument("--output-folder", type=str, default="outputs")
parser.add_argument("--configs-folder", type=str, default="configs/")

if __name__ == '__main__':
    args = parser.parse_args()
    if args.n % 2 != 1:
        logger.warning('Even number of samples ({args.n}) may cause conflicts in majority voting.')
    setting_config_path = args.setting_config + ".yaml" if not args.setting_config.endswith(".yaml") else args.setting_config
    with open(f"{args.configs_folder}/setting/{setting_config_path}", 'r') as f:
        setting_config = yaml.safe_load(f)

    for config_path in args.judge_configs:
        config_path = config_path + ".yaml" if not config_path.endswith(".yaml") else config_path
        with open(f"{args.configs_folder}/models/{config_path}", 'r') as f:
            judge_config = yaml.safe_load(f)
            
        
        judge_config["n"] = judge_config.get("n", args.n)
        logger.info(f"Running config: {config_path}")
        run(judge_config, setting_config, config_path.replace('.yaml', ''), skip_existing=args.skip_existing, output_folder=args.output_folder)