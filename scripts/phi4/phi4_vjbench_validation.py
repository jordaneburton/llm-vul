import os
import json
import sys
import re
from pathlib import Path
import multiprocessing

PHI4_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep
sys.path.insert(1, PHI4_DIR + '../')  # utils file

from util import cve_test_java_file, cve_compile_java_file, VJBENCH_DIR, ROOT_PATH, cve_name_to_int

validation_folder = os.path.join(ROOT_PATH, "Model_patches", "validation", "phi4_vjbench")
if not os.path.exists(validation_folder):
    os.makedirs(validation_folder, exist_ok=True)

def validate_phi4_vjbench(vul_id):
    raw_vul_id = "VUL4J-{}".format(cve_name_to_int[vul_id])
    results = phi4_result["data"][vul_id]
    prompt = results["input"]
    outputs = results["output"]
    validation_result = []
    for output in outputs:
        vdict = {"patch": output, "correctness": ""}
        if cve_compile_java_file(VJBENCH_DIR, compile_cmd):
            vdict["correctness"] = "compile_success"
            if cve_test_java_file(VJBENCH_DIR, test_cmd):
                vdict["correctness"] = "test_success"
        validation_result.append(vdict)
    results["validation_result"] = validation_result
    phi4_result["data"][vul_id] = results

if __name__ == '__main__':
    phi4_output_file = os.path.join(ROOT_PATH, "Model_patches", "model_output", "phi4", "output-phi4-original.json")
    with open(phi4_output_file, "r") as f:
        phi4_result = json.load(f)
    p = multiprocessing.Pool(1)
    p.map(validate_phi4_vjbench, cve_name_to_int.keys())