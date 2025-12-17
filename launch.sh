#!/bin/sh
#
#SBATCH --verbose
#SBATCH --time=02-00:00:00
#SBATCH --nodes=1
#SBATCH --tasks-per-node=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=8GB
#SBATCH --output=slurm.out

module purge
module load nextflow/25.10.2
module load anaconda3/2025.06 

run_dir_path=${1:-"/scratch/eb167/GENEFLOW/data/sequencers/250822_A01097_0361_ANOVATEST1"}
fcid=${2:-"ANOVATEST1"}
conf=${3:-"test-novaseq.config"}

log_dir="$SCRATCH/GENEFLOW/out/logs/${fcid}/pipeline"

nextflow \
  -log ${log_dir}/nextflow.log \
  run main.nf \
  -c nextflow.config -profile hpc \
  --run_dir_path $run_dir_path \
  --trace_file_path ${log_dir}/trace.txt \
  -with-report ${log_dir}/${fcid}_report.html

