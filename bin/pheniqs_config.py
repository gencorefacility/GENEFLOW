#!/usr/bin/env python3
# usage: python3 pheniqs_config.py <fcid> <lane_num> <cpus: defaults to 1 if not provided>

import datetime
import os
import sys
from xml.dom import minidom
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
seq_id = os.path.basename(run_dir_path).split('_')[1]

pheniqs_conf = {
    "CN": "CGSB",
    "DT": str(datetime.datetime.now()),
    "PI": "300",  # what is this?
    "PL": "ILLUMINA",
    "PM": seq_id,
    "base input path": f"{alpha}lane/{fcid}",
    "decoder": "mdd",
    "include filtered": False,
    "threads": int(cpus),
    "channel": [],
    "input": []
}

run = get_run_info(fcid)
lane = next(lane for lane in get_lanes(run['id'])['lanes'] if lane["lane_number"] == int(lane_num))
pool = get_pool(lane['id'])
libs = get_libraries(pool['id'])
lib = libs[0]['library']
barcodes = get_lib_barcodes(lib['id'])

## Build input, token, template, multiplex_barcode
## Get this from RunInfo.xml in run dir
## Use the barcode objects from TW as well to get 
## sequence length, offset, etc. 
non_index_read_count = 0
i = 0
token = []
template = []
multiplex_barcode = []

runinfo = minidom.parse(f"{run_dir_path}/RunInfo.xml")
nibbles = runinfo.getElementsByTagName('Read')
nib_number = 0

lane_folder = f"{alpha}lane/{fcid}/{lane['lane_number']}"

for nib in nibbles:
    # Build the input list
    nib_number += 1
    fastq_file = f"{lane_folder}/{fcid}_l0{lane['lane_number']}.{nib_number}.fastq.gz"
    pheniqs_conf['input'].append(fastq_file)

    # Build the barcode, template, and token lists
    if nib.attributes['IsIndexedRead'].nodeValue == "N":
        non_index_read_count += 1
        token.append(f"{int(nib.attributes['Number'].nodeValue) - 1}::")
        template.append(str(i))
        i += 1

    for barcode in barcodes:
        if barcode['barcode_location'] == int(nib.attributes['Number'].nodeValue):
            barcode_position = barcode['barcode_position'] - 1
            barcode_length = len(barcode['barcode_sequence'])
            token.append(f"{int(nib.attributes['Number'].nodeValue) - 1}:{barcode_position}:{barcode_position + barcode_length}")
            multiplex_barcode.append(str(i))
            i += 1

pheniqs_conf.update({
    'token': token,
    'multiplex barcode': multiplex_barcode,
    'template': template
})

output_path = f"{alpha}sample/{fcid}/{lane['lane_number']}"
os.makedirs(output_path, exist_ok=True)
pheniqs_conf["base output path"] = output_path

channel = {
    "DS": "undetermined",
    "LB": "undetermined_library",
    "PU": f"{fcid}:{lane['lane_number']}:undetermined",
    "RG": f"{fcid}:{lane['lane_number']}:undetermined",
    "SM": "undetermined_sample",
    "output": [f"{fcid}_l0{lane['lane_number']}_n0{x+1}_undetermined.fastq.gz" for x in range(non_index_read_count)],
    "undetermined": True
}

pheniqs_conf["channel"].append(channel)

## Make Library Channels:
for l in libs:
    lib_id = l['library']['id']
    lib = get_library(lib_id)
    barcodes = get_lib_barcodes(lib_id)

    ## Reverse compliment barcode sequence if barcode location == 3 (Index 2) and
    ## pool.index_is_revcom is True. For now, we don't care which index in TuboWeb
    ## it is, that refers to the index which was encoded first or second. We know
    ## that if you need to reverse complement any barcode, it's the one on Index 2,
    ## regardless of what order it was encoded in TuboWeb.  
    barcode_sequences = [reverse_complement(bc['barcode_sequence'].upper())
                         if any(b['revcom'] is True for b in pool['reverse_complement']) and bc['barcode_location'] == 3
                         else bc['barcode_sequence'].upper()
                         for bc in sorted(barcodes, key=itemgetter('barcode_location'))]

    channel = {
        "DS": lib['name'],
        "LB": lib['name'],
        "PU": f"{fcid}:{lane['lane_number']}:{':'.join(barcode_sequences)}",
        "RG": f"{fcid}:{lane['lane_number']}:{':'.join(barcode_sequences)}",
        "SM": lib['name'],
        "barcode": barcode_sequences,
        "concentration": 1,
        "output": [f"{fcid}_l0{lane['lane_number']}_n0{x+1}_{lib['name']}.fastq.gz" for x in range(non_index_read_count)]
    }

    pheniqs_conf["channel"].append(channel)

with open('demux.json', 'w') as outfile:
    json.dump(pheniqs_conf, outfile, indent=4)
    
print("Pheniqs config file created for lane {}: demux.json".format(lane['lane_number']))
