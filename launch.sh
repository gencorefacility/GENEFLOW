#!/bin/sh
#
#SBATCH --verbose
#SBATCH --time=7-00:00:00
#SBATCH --nodes=1
#SBATCH --tasks-per-node=1
#SBATCH --cpus-per-task=3
#SBATCH --mem=6GB
#SBATCH --mail-user=netID@nyu.edu

module purge
module load nextflow/23.04.1

run_dir_path=$1
fcid=$2
entry=$3

log_dir="/scratch/gencore/GENEFLOW/alpha/logs/${fcid}/pipeline"

nextflow_command="nextflow \
  -log ${log_dir}/nextflow.log run /home/gencore/SCRIPTS/GENEFLOW/main.nf \
  -c /home/gencore/SCRIPTS/GENEFLOW/nextflow.config \
  --run_dir_path $run_dir_path \
  --trace_file_path ${log_dir}/trace.txt \
  -with-report ${log_dir}/${fcid}_report.html"

# Check if the third parameter (entry point) is provided and append to the command
if [ ! -z "$entry" ]; then
  nextflow_command="$nextflow_command -entry $entry"
fi

# Execute the command
eval $nextflow_command

