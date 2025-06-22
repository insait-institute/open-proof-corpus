#!/bin/bash
#SBATCH --partition=batch       # Specify the partition
#SBATCH --constraint=type-gpu   # Or type-gpu for GPU nodes
#SBATCH --ntasks=1              # Number of tasks (total)
#SBATCH --cpus-per-task=16       # Number of CPU cores (threads) per task
#SBATCH --mem-per-cpu=16G       # Memory limit per CPU core (there is no --mem-per-task)
#SBATCH --time=24:00:00         # Job timeout
#SBATCH --output=best_of_n.log  # Redirect stdout to a log file
#SBATCH --error=best_of_n.err   # Redirect stderr to a separate error log file
#SBATCH --gpus=h200:1


export CUDA_HOME=/opt/modules/nvidia-cuda-12.8.0/
export CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7

conda activate opc
bash ./slurm/setup.sh

python runs/best_of_n_actor.py
python runs/best_of_n_critic.py --continuous
