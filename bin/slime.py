#!/usr/bin/env python3

import os
import re
import sys
import requests
import json
import glob
import smtplib
import logging
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from xml.dom import minidom
from shutil import copyfile, copytree
from config import tw_api_root, tw_user, tw_api_key, gmail_user, gmail_pwd, raw_run_root, alpha


logging.basicConfig(
    filename='slime.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)

def send_email(recipient, subject, body):
    FROM = gmail_user
    TO = recipient if isinstance(recipient, list) else [recipient]
    SUBJECT = "GENEFLOW: " + subject
    TEXT = body

    # Create the email message
    msg = MIMEMultipart('alternative')
    msg['From'] = FROM
    msg['To'] = ", ".join(TO)
    msg['Subject'] = SUBJECT

    # Attach the email content, encoded in UTF-8
    msg.attach(MIMEText(TEXT, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(gmail_user, gmail_pwd)
            server.sendmail(FROM, TO, msg.as_string())

    except Exception as e:
        print("Failed to send email:", str(e))


def get_run_info(fcid):
    run_url = f"{tw_api_root}flowcell/illumina/{fcid}/"
    params = {"username": tw_user, "api_key": tw_api_key}
    response = requests.get(run_url, params=params)
    run_data = response.json()
    return run_data


def get_num_lanes(fcid):
    # New way: check locally
    # Reflects actual data on disk 
    # (won’t silently mis-count if LIMS is stale or a lane failed).
    run_dir = get_run_dir(fcid)['run_dir']

    # 1) Illumina: check for BaseCalls/L### dirs
    illumina_base = os.path.join(run_dir, 'Data', 'Intensities', 'BaseCalls')
    if os.path.isdir(illumina_base):
        lanes = [d for d in os.listdir(illumina_base) 
                 if re.match(r'^L\d{3}$', d)]
        if lanes:
            return len(lanes)

    # 2) Aviti: look in Location for .loc files like L1R19C02S1.loc
    loc_dir = os.path.join(run_dir, 'Location')
    if os.path.isdir(loc_dir):
        # extract the lane number after the leading “L”
        lane_ids = set()
        for fname in os.listdir(loc_dir):
            m = re.match(r'^L(\d+)R\d+C\d+S\d+\.loc$', fname)
            if m:
                lane_ids.add(m.group(1))
        if lane_ids:
            return len(lane_ids)


def get_lanes(run_id):
    lanes_url = f"{tw_api_root}flowcell/{run_id}/lanes/"
    params = {"username": tw_user, "api_key": tw_api_key}
    response = requests.get(lanes_url, params=params)
    lanes_data = response.json()
    return lanes_data


def get_pool(lane_id):
    pools_url = f"{tw_api_root}lane/{lane_id}/librarypools/"
    params = {"username": tw_user, "api_key": tw_api_key}
    response = requests.get(pools_url, params=params)
    pools_data = response.json()
    
    if len(pools_data["librarypools"]) == 0:
        # todo: check if it's PHiX
        print(f"There is no Library Pool for lane: {lane_id}")
        return None

    pool_id = pools_data["librarypools"][0]["id"]
    pool_url = f"{tw_api_root}librarypool/{pool_id}/"
    response = requests.get(pool_url, params=params)
    pool_data = response.json()

    return pool_data


def get_libraries(pool_id):
    lpc_url = f"{tw_api_root}librarypool/{pool_id}/librarypoolconcentrations/"
    params = {"username": tw_user, "api_key": tw_api_key}
    response = requests.get(lpc_url, params=params)
    lpc_data = response.json()
    return lpc_data["librarypoolconcentrations"]


def get_library(lib_id):
    url = f"{tw_api_root}library/{lib_id}/"
    params = {"username": tw_user, "api_key": tw_api_key}
    response = requests.get(url, params=params)
    data = response.json()
    return data


def get_lib_barcodes(lib_id):
    lbc_url = f"{tw_api_root}library/{lib_id}/barcodes/"
    params = {"username": tw_user, "api_key": tw_api_key}
    response = requests.get(lbc_url, params=params)
    lbc_data = response.json()

    barcodes = []
    for bc in lbc_data["barcodes"]:
        url = f"{tw_api_root}barcode/{bc['id']}/"
        response = requests.get(url, params=params)
        data = response.json()
        barcodes.append(data)

    return barcodes


def get_run_dir(fcid):
    query = f"{raw_run_root}/*/*{fcid}"
    print("Locating run dir: ", query)
    run_dir = glob.glob(os.path.join(query))
    
    if len(run_dir) != 1:
        print({'status': 'error', 'msg': f'len(run_dir) != 1, found {len(run_dir)}; fcid = {fcid}'})
        sys.exit(1)
    
    print("Found run dir: ", run_dir[0])
    return {'status': 'success', 'run_dir': run_dir[0]}


def check_do_merge(fcid):
    run = get_run_info(fcid) 
    run_type = run["run_type_name"]
    return (
        "NextSeq" in run["sequencer"]["name"] or  # Sequencer is NextSeq
        ( 
            "NovaSeq" in run["sequencer"]["name"] and  # Sequencer is NovaSeq
            not run_type.startswith("XP")  # Run type does not start with "XP"
        ) or
        (
            "Aviti" in run["sequencer"]["name"] and  # Sequencer is Aviti
            run_type.startswith("ML - ")  # Run type starts with "ML"
        )
    )


# Check if the pool in this lane needs to be demultiplexed or not
def check_demux(fcid, lane_num):
    try:
        run_id = get_run_info(fcid)["id"]
        lanes = get_lanes(run_id)['lanes']
        lane = next(lane for lane in lanes if lane["lane_number"] == int(lane_num))
        pool = get_pool(lane["id"])

        # "pool.get("no_demux", True) is not False" checks if pool.no_demux is True, None, 
        # or if it does not exist in the pool. It defaults to True.
        # Using "is not False" ensures that we cover the cases where pool.no_demux is True or None.
        # If you simply use "is True", it won't cover the scenario when pool.no_demux is None or doesn't exist in pool.
        # Thus, return True if pool.no_demux is True, None, if there's an error, or if pool.no_demux doesn't exist.
        return pool is None or pool.get("no_demux", True) is not False
    except Exception as e:
        print(f"An error occurred: {e}")
        # In case of error, return True
        #return True  
        sys.exit(1)


def reverse_complement(seq):
    complement = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C'}
    reverse_complement = ''.join(complement[base] for base in reversed(seq))
    return reverse_complement


def set_first_demux_undetermined_pct(fcid, num, val):
    logging.debug(f'{fcid}: Setting first demux undetermined pct')
    print("Setting first demux undetermined pct")
    url = f"{tw_api_root}flowcell/illumina/{fcid}/set_first_demux_undetermined_pct/{num}"
    params = {"username": tw_user, "api_key": tw_api_key, "value": val}
    response = requests.get(url, params=params)
    data = response.json()
    return data
    
    
def get_first_demux_undetermined_pct(fcid, num):
    url = f"{tw_api_root}flowcell/illumina/{fcid}/get_first_demux_undetermined_pct/{num}"
    params = {"username": tw_user, "api_key": tw_api_key}
    response = requests.get(url, params=params)
    data = response.json()
    return data

def run_redemux(fcid):
    print("running redemux")
    logging.debug(f'{fcid}: running redemux')
    # Define the base command and parameters
    root_log_dir = alpha + "/logs/"
    
    base_cmd = 'sbatch'
    output_cmd = f"--output={root_log_dir}/{fcid}/pipeline/slurm-%j-redemux.out"
    error_cmd = f"--error={root_log_dir}/{fcid}/pipeline/slurm-%j-redemux.err"
    job_name_cmd = f"--job-name=GENEFLOW_MANAGER_\\({fcid}\\)_redemux"
    
    # Find the run directory
    find_cmd = f"cd {raw_run_root}; find -maxdepth 2 -type d -name '*{fcid}'"
    rundir_cmd = f"rundir=$({find_cmd}); echo rundir = $rundir;"
    
    # Construct the launch command with the found run directory
    # TODO: make path to launch.sh a param in the config?
    launch_cmd = f"/home/gencore/SCRIPTS/GENEFLOW/launch.sh {raw_run_root}/$rundir {fcid} demux"
    
    # Combine the commands
    full_cmd = f"{rundir_cmd} {base_cmd} {output_cmd} {error_cmd} {job_name_cmd} {launch_cmd}"
    
    # Execute the command and get the output
    demux_output = subprocess.getoutput(full_cmd)
    
    # Format and print the output
    formatted_output = f"\n{full_cmd}\n{demux_output}\n"
    print(f"Auto-Redemuxing\n{formatted_output}")
    logging.debug(f'{fcid}: Auto-Redemuxing\n{formatted_output}')
    send_email(["mk5636@nyu.edu"], "ERROR For {}".format(fcid), f"Auto-Redemuxing\n{formatted_output}")
    
def set_pool_index_revcom(pool_id, i):
    url = f"{tw_api_root}librarypool/{pool_id}/setindexisrevcom/{i}"
    params = {"username": tw_user, "api_key": tw_api_key}
    response = requests.get(url, params=params)
    data = response.json()
    return data


def set_run_index_revcom(fcid, status):
    run = get_run_info(fcid)
    logging.debug(f'{fcid}: set_run_index_revcom, run pre set_run_index_revcom: {run}')
    #send_email(["mk5636@nyu.edu"], "ERROR For {}".format(fcid), "set_run_index_revcom, run pre set_run_index_revcom: {}".format(str(run)))
    url = f"{tw_api_root}flowcell/illumina/{fcid}/setindexisrevcom/{status}"
    params = {"username": tw_user, "api_key": tw_api_key}
    response = requests.get(url, params=params)
    data = response.json()
    run = get_run_info(fcid)
    logging.debug(f'{fcid}: set_run_index_revcom, run pre set_run_index_revcom response: {data}; run post set_run_index_revcom: {run}')
    #send_email(["mk5636@nyu.edu"], "ERROR For {}".format(fcid), 'set_run_index_revcom response: {}\nrun post set_run_index_revcom: {}'.format(data, run))
    return data


def flip_index2_revcom(fcid):
    """
    Turn on/off revcom for index 2 for the run and all pools.
    Right now we just turn off, but we can set this to be a parameter
    or to toggle it based on the current state.
    """
    logging.debug(f'{fcid}: flipping index2 revcom')
    print("flipping index2 revcom")
    run = get_run_info(fcid)
    lanes = get_lanes(run['id'])
    for lane in lanes['lanes']:
        pool_o = get_pool(lane['id'])
        pool = pool_o['id']
        logging.debug(f'{fcid}: lane = {lane}; pool = {pool_o}')
        #send_email(["mk5636@nyu.edu"], "ERROR For {}".format(fcid), 'lane = {}; pool = {}'.format(lane, pool_o))
        # turn off revcom for index 2 for all pools
        r = set_pool_index_revcom(pool, 0)
        print("r: {}".format(r))
        pool_o = get_pool(lane['id'])
        logging.debug(f'{fcid}: set_pool_index_revcom(pool, 0) response = {r}, pool = {pool_o}')
        #send_email(["mk5636@nyu.edu"], "ERROR For {}".format(fcid), "set_pool_index_revcom(pool, 0), pool = {}".format(pool_o))
    # turn off revcom for index 2 for the run
    set_run_index_revcom(fcid, 0)
    print("Finished flipping index2 revcom")

def change_permissions_recursive(path, mode):
    # Change the directory's own permissions
    os.chmod(path, mode)

    # Traverse all files and directories inside the given directory
    for root, dirs, files in os.walk(path):
        for dir in dirs:
            # Change permissions for each directory
            os.chmod(os.path.join(root, dir), mode)

        for file in files:
            # Change permissions for each file
            os.chmod(os.path.join(root, file), mode)

