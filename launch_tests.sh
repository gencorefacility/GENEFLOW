#!/bin/sh
#
#SBATCH --verbose
#SBATCH --time=168:00:00
#SBATCH --nodes=1
#SBATCH --tasks-per-node=1
#SBATCH --cpus-per-task=6
#SBATCH --mem=10000
#SBATCH --output=test.log
module purge
module load nextflow/25.10.2
module load anaconda3/2025.06

fcid=000000000-TEST1
conf=test-miseq.config

log_dir="/scratch/gencore/GENEFLOW/alpha/logs/${fcid}/pipeline"

nextflow_command="nextflow \
  -log ${log_dir}/nextflow.log run /home/gencore/SCRIPTS/GENEFLOW/main.nf \
  -c /home/gencore/SCRIPTS/GENEFLOW/nextflow.config \
  -c /home/gencore/SCRIPTS/GENEFLOW/${conf} -profile hpc \
  --test \
  --trace_file_path ${log_dir}/trace.txt \
  -with-report ${log_dir}/${fcid}_report.html"

# Execute the command
eval $nextflow_command

