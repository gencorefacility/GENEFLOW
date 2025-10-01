#!/bin/bash

## USAGE: sh merge.sh <fcid> <alpha>

fcid=$1
alpha=${2:-/scratch/mk5636/alpha}

echo "merge.sh: fcid: $fcid"
echo "merge.sh: alpha: $alpha"

# since we're merging, can use lane 1 to check if run is demuxed or not
no_demux=$(python3 -c "from slime import check_demux;r=check_demux('${fcid}', 1);print(str(r).lower())" 2>&1)

# Check if Python script executed successfully immediately after execution
if [ $? -ne 0 ]; then
  echo "merge.sh: ERROR: Failed to assign no_demux: $no_demux"
  exit 1
fi

echo "merge.sh: no_demux: $no_demux"

if [ "$no_demux" == "true" ]; then
    folderType="lane"
else
    folderType="sample"
fi

path="${alpha}/${folderType}/${fcid}"
out_dir="${alpha}/merged/${fcid}/merged"

# Ensure output directory exists
mkdir -p "${out_dir}"

# Clear the directory if it already exists with data
rm -f "${out_dir}"/*

# Get number of lanes
num_lanes=$(find "${path}" -mindepth 1 -maxdepth 1 -type d | wc -l)

for file in $(find "${path}/1/" -name "*fastq.gz")
do
    if [ "$no_demux" == "true" ]; then
        id=$(basename "${file%%.fastq.gz}" | cut -d '.' -f2) ################### needs to be same as below
        merged_file="${fcid}_${id}.fastq.gz"
    else
        id=$(echo "${file}" | grep -oP '_n0[1-4]_.+\.fastq\.gz' | sed -n 's/.*\(_n0[1-4]_.\+\)\.fastq\.gz/\1/p')
        echo "id: $id"
        merged_file="${fcid}_${id}.fastq.gz"
    fi

    # Loop through the number of lanes to get inputs
    for lane in $(seq 1 $num_lanes); do
        input[$lane]=$(find "${path}/${lane}/" -name "*${id}.fastq.gz")
        echo "input[$lane]: ${input[$lane]}"
    done

    # Merge files
    cat "${input[@]}" > "${out_dir}/${merged_file}"

    echo "Created ${merged_file}"
    echo '--'
done
