#!/bin/sh
#
#SBATCH --verbose
#SBATCH --time=168:00:00
#SBATCH --nodes=1
#SBATCH --tasks-per-node=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=10000
#SBATCH --mail-user=netID@nyu.edu

module purge
module load nextflow/23.04.1

run_dir_path=$1
fcid=$2
entry="${3:+-entry $3}"

log_dir="/scratch/gencore/GENEFLOW/alpha/logs/${fcid}/pipeline"

nextflow \
  -log ${log_dir}/nextflow.log \
  run gencorefacility/GENEFLOW \
  -c /home/gencore/SCRIPTS/GENEFLOW/nextflow.config \
  --run_dir_path $run_dir_path \
  --trace_file_path ${log_dir}/trace.txt \
  -with-report ${log_dir}/${fcid}_report.html \
  ${entry}

