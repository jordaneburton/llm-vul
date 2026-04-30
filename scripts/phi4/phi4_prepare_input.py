import os
import json
from pathlib import Path
import sys
import re

PHI4_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep
JAVA_DIR = PHI4_DIR + '../../jasper/'
sys.path.insert(1, PHI4_DIR + '../')  # utils file

from util import vjbench_bug_id_list, vul4j_bug_id_list, cve_int_to_name

bug_range_list = vjbench_bug_id_list + vul4j_bug_id_list

def command(cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, err = process.communicate()
    if output != b'' or err != b'':
        print(output)
        print(err)
    return output, err

def generate_phi4_input(output_file, trans):
    phi4_input = {'config': 'phi4', 'data': {}}
    for vul_int in bug_range_list:
        vul_id = "VUL4J-{}".format(vul_int)
        if vul_int > 1000:
            vul_id = cve_int_to_name[vul_int]
        VUL_FOLDER = os.path.join(PHI4_DIR + '../../VJBench-trans', vul_id)
        bug_location_file = os.path.join(VUL_FOLDER, "buggyline_location.json")
        with open(bug_location_file, 'r') as f:
            buggy_line_dict = json.load(f)
        buggy_line_list = buggy_line_dict[trans]
        buggy_file = os.path.join(VUL_FOLDER, "{}_{}.java".format(vul_id, trans))
        phi4_input['data'][vul_id] = {
            'loc': buggy_line_list,
            'input': buggy_file,
        }
    json.dump(phi4_input, open(output_file, 'w'), indent=2)

if __name__ == "__main__":
    for trans in ["structure_change_only", "rename_only", "rename+code_structure", "original"]:
        input_folder = os.path.join(PHI4_DIR, "inputs")
        if not os.path.exists(input_folder):
            os.mkdir(input_folder)
        input_file = os.path.join(PHI4_DIR, "inputs", "input-{}.json".format(trans))
        generate_phi4_input(input_file, trans)