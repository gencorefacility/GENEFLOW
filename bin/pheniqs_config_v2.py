#!/usr/bin/env python3
# usage: python3 pheniqs_config.py <fcid> <lane_num> <cpus: defaults to 1 if not provided>

import datetime
import os
import sys
from xml.dom import minidom
import json
from operator import itemgetter
from slime import *
from config import alpha

# Ensure there are at least 2 arguments provided (for fcid and lane_num)
if len(sys.argv) < 3:
    raise Exception('Not enough arguments provided. Please provide fcid and lane_num as a minimum')

fcid = sys.argv[1]
lane_num = sys.argv[2]

# If cpus argument is provided, use it. If not, default to '1'
cpus = sys.argv[3] if len(sys.argv) > 3 else '1'

run_dir_path = get_run_dir(fcid)['run_dir']

run = get_run_info(fcid)
lane = next(lane for lane in get_lanes(run['id'])['lanes'] if lane["lane_number"] == int(lane_num))
pool = get_pool(lane['id'])
libs = get_libraries(pool['id'])
lib = libs[0]['library']
barcodes = get_lib_barcodes(lib['id'])

# GLOBAL CONFIG
pheniqs_conf = {
    "CN": "CGSB",
    "DT": str(datetime.datetime.now()),
    "PI": "300",  # what is this?
    "PL": run['sequencer']['manufacturer'].upper(),
    "PM": run['sequencer']['name'],
    "base input url": f"{alpha}lane/{fcid}",
    "filter incoming qc fail": True,
    "flowcell id": fcid,
    "flowcell lane number": int(lane_num),
    "threads": int(cpus),
    "sample": {"algorithm": "mdd", "codec": {}, "transform": {}},
    "input": [],
    "template": {"transform": {}}
}

## Build input, token, template
## Get this from RunInfo.xml in run dir
## Use the barcode objects from TW as well to get 
## sequence length, offset, etc. 
non_index_read_count = 0
token = []
template = []
nib_number = 0
lane_folder = f"{alpha}lane/{fcid}/{lane['lane_number']}"

if run['sequencer']['manufacturer'] == "Element":

    pheniqs_conf['PL'] = "UNKNOWN"

    # Define the order in which you want to process the keys
    desired_order = ['R1', 'I1', 'I2', 'R2']

    # Load the JSON file
    with open(f'{run_dir_path}/RunParameters.json', 'r') as file:
        data = json.load(file)

    # Access the "Cycles" field
    cycles = data.get('Cycles', {})

    # Process the keys in the desired order
    for key in desired_order:
        if key in cycles and cycles[key] != 0:
            nib_number += 1
            fastq_file = f"{lane_folder}/{fcid}_l0{lane['lane_number']}.{nib_number}.fastq.gz"
            pheniqs_conf['input'].append(fastq_file)
            
            if key in ["R1", "R2"]:
                non_index_read_count += 1
                template.append(f"{nib_number - 1}::")
            
            for barcode in barcodes:
                if barcode['barcode_location'] == nib_number:
                    token.append(f"{nib_number - 1}:{barcode['barcode_position'] - 1}:{barcode['barcode_position'] - 1 + len(barcode['barcode_sequence'])}")

elif run['sequencer']['manufacturer'] == "Illumina":
        
    runinfo = minidom.parse(f"{run_dir_path}/RunInfo.xml")
    nibbles = runinfo.getElementsByTagName('Read')

    for nib in nibbles:
        # Build the input list
        nib_number += 1
        fastq_file = f"{lane_folder}/{fcid}_l0{lane['lane_number']}.{nib_number}.fastq.gz"
        pheniqs_conf['input'].append(fastq_file)

        # Build the barcode, template, and token lists
        if nib.attributes['IsIndexedRead'].nodeValue == "N":
            non_index_read_count += 1
            template.append(f"{int(nib.attributes['Number'].nodeValue) - 1}::")

        for barcode in barcodes:
            if barcode['barcode_location'] == int(nib.attributes['Number'].nodeValue):
                token.append(f"{int(nib.attributes['Number'].nodeValue) - 1}:{barcode['barcode_position'] - 1}:{barcode['barcode_position'] - 1 + len(barcode['barcode_sequence'])}")

pheniqs_conf['sample']['transform']['token'] = token
pheniqs_conf['template']['transform']['token'] = template

output_path = f"{alpha}sample/{fcid}/{lane['lane_number']}"
os.makedirs(output_path, exist_ok=True)
pheniqs_conf["base output url"] = output_path

# Make undetermined channel:
channel = {
    "DS": "undetermined",
    "LB": "undetermined_library",
    "SM": "undetermined_sample",
    "output": [f"{fcid}_l0{lane['lane_number']}_n0{x+1}_undetermined.fastq.gz" for x in range(non_index_read_count)],
}
pheniqs_conf["sample"]["undetermined"] = channel
#pheniqs_conf["sample"]["codec"]["undetermined"] = channel??

# Write just a list of expected barcodes
barcode_list = []

# Make Library Channels:
for l in libs:
    lib_id = l['library']['id']
    lib = get_library(lib_id)
    barcodes = get_lib_barcodes(lib_id)

    barcode_sequences = [reverse_complement(bc['barcode_sequence'].upper())
                         if any(b['revcom'] is True for b in pool['reverse_complement']) and bc['barcode_location'] == 3
                         else bc['barcode_sequence'].upper()
                         for bc in sorted(barcodes, key=itemgetter('barcode_location'))]

    channel = {
        "DS": lib['name'],
        "LB": lib['name'],
        "SM": lib['name'],
        "barcode": barcode_sequences,
        "concentration": 1,
        "output": [f"{fcid}_l0{lane['lane_number']}_n0{x+1}_{lib['name']}.fastq.gz" for x in range(non_index_read_count)]
    }
    pheniqs_conf["sample"]["codec"][lib['name']] = channel
    barcode_list.append(barcode_sequences)

with open(f'demux.json', 'w') as outfile:
    json.dump(pheniqs_conf, outfile, indent=4)
# Write barcode_list to expected_barcodes.txt, one element per line

with open('expected_barcodes.txt', 'w') as f:
    for item in barcode_list:
            f.write('-'.join(item) + '\n')

print("Pheniqs2 config file created for lane {}: demux.json".format(lane['lane_number']))
print("expected_barcodes.txt file created for lane {}".format(lane['lane_number']))

