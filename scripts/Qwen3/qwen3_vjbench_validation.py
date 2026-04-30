import os
import json
import subprocess
import sys
import re
from pathlib import Path

# Add the scripts/ directory to the path so we can import util.py
QWEN3_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep
sys.path.insert(1, QWEN3_DIR + '../')

from util import cve_test_java_file, cve_compile_java_file, VJBENCH_DIR, info_json, vjbench_json, ROOT_PATH
from util import extract_correct_method_code, translate_code, cve_name_to_int

MODEL_NAME = 'Qwen3-4B'

# Folder where validation result JSON files will be saved
validation_folder = os.path.join(ROOT_PATH, "Model_patches", "validation", "qwen3_vjbench")
os.makedirs(validation_folder, exist_ok=True)


def validate_qwen3_vjbench(vul_id, trans, qwen3_result, output_file_path):
    # Skip if Qwen3 produced no output for this vulnerability
    if vul_id not in qwen3_result["data"]:
        return

    # Load the vulnerability location metadata (buggy file path, line numbers, etc.)
    with open(info_json, "r") as f:
        all_info_list = json.load(f)

    buggy_file_path = None
    for info in all_info_list:
        # VJBench IDs are stored internally as VUL4J-XXXX, so convert the name
        raw_vul_id = "VUL4J-{}".format(cve_name_to_int[vul_id])
        if info["vul_id"] == raw_vul_id:
            # Get the relative path to the buggy Java file within the project
            buggy_file_path = info["buggy_file"]
            # Line numbers of the full buggy method (used to splice in the patch)
            buggy_method_start = info["buggy_method_with_comment"][0][0]
            buggy_method_end = info["buggy_method_with_comment"][0][1]
            buggy_line_start = info["buggy_line"][0][0]
            # Build the absolute path to the cloned project on disk
            project_path = os.path.join(VJBENCH_DIR, vul_id)
            buggy_file_path = os.path.join(project_path, buggy_file_path)
            # Handle single-line and multi-line bugs
            buggy_line_end = buggy_line_start if len(info["buggy_line"][0]) == 1 else info["buggy_line"][0][1]

            # Load the compile and test commands for this project
            with open(vjbench_json, "r") as f:
                vjbench_info = json.load(f)
            compile_cmd = vjbench_info[vul_id]["compile_cmd"]
            test_cmd = vjbench_info[vul_id]["test_cmd"]

            # Reset the buggy file to its original state using git before each validation run
            # so previous patch attempts don't bleed into the next one
            restore_cmd = "git checkout HEAD {}".format(vjbench_info[vul_id]["buggy_file_path"])
            p = subprocess.Popen(restore_cmd.split(), cwd=project_path, stdout=subprocess.PIPE)
            p.wait()

    # If no matching vulnerability was found in the metadata, skip
    if buggy_file_path is None:
        return

    # Read the original buggy file contents — we'll restore these after each patch attempt
    with open(buggy_file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    validation_result = []

    # Get the correct code surrounding the buggy method from the ground truth
    # so we know exactly where to splice in Qwen3's generated patch
    code_before, code_after, flag = extract_correct_method_code(vul_id, trans)
    if not flag:
        return

    results = qwen3_result["data"][vul_id]
    if "output" not in results:
        return
    outputs = results["output"]  # list of 10 patch candidates from Qwen3

    # Path to the JSON file where this vulnerability's validation results are saved
    validation_result_file = os.path.join(
        validation_folder,
        "output-{}-{}_{}.json".format(MODEL_NAME, trans, vul_id)
    )

    # Resume from where we left off if validation was previously interrupted
    existing_validation_result_length = -1
    if os.path.exists(validation_result_file):
        with open(validation_result_file, "r") as f:
            existing_validation_result = json.load(f)["validation_result"]
            existing_validation_result_length = len(existing_validation_result)
            validation_result = existing_validation_result

    for i, generated_code in enumerate(outputs):
        # Skip patches that were already validated in a previous run
        if i < existing_validation_result_length:
            continue

        generated_code = generated_code.strip()
        vdict = {"patch": generated_code, "correctness": ""}

        # Normalize whitespace for deduplication comparison
        check_deduped = re.sub(r'\s+', '', generated_code).strip()

        # Check if this patch is identical to one we already validated
        # If so, reuse that result instead of recompiling
        duplicated = False
        for v in validation_result:
            if re.sub(r'\s+', '', v["patch"]).strip() == check_deduped:
                duplicated = True
                vdict["correctness"] = v["correctness"]
                # For transformed versions, carry over the back-translated code
                if trans not in ("original", "structure_change_only"):
                    vdict["translated"] = v.get("translated", "")
                validation_result.append(vdict)
                results["validation_result"] = validation_result
                with open(validation_result_file, "w") as f:
                    json.dump(results, f, indent=4)
                print("duplicated")
                break

        if not duplicated:
            # For renamed transformations, translate the renamed identifiers back
            # to the original variable names before compiling against the real project
            if trans not in ("original", "structure_change_only"):
                generated_code = translate_code(generated_code, vul_id)
                vdict["translated"] = generated_code

            # Splice the generated patch into the buggy file:
            # keep lines before the method, insert the fix, keep lines after the method
            with open(buggy_file_path, "w", encoding="utf-8", errors="ignore") as f:
                f.writelines(lines[:buggy_method_start - 1])  # code before the method
                f.writelines(code_before)                      # method signature / opening
                f.write(generated_code)                        # Qwen3's patch
                f.writelines(code_after)                       # closing of the method
                f.writelines(lines[buggy_method_end:])         # rest of the file

            # Step 1: try to compile the patched project
            print("validation: start compiling")
            if not cve_compile_java_file(project_path, compile_cmd):
                vdict["correctness"] = "uncompilable"
                print("validation: compile failed")
            else:
                vdict["correctness"] = "compile_success"
                # Step 2: if it compiled, run the project's test suite
                print("validation: start testing")
                test_result = cve_test_java_file(project_path, test_cmd)
                if test_result == 1:
                    vdict["correctness"] = "test_success"   # patch fixes the vulnerability
                    print("validation: test success")
                elif test_result == 2:
                    vdict["correctness"] = "test_timeout"   # tests ran too long
                    print("test_timeout")

            validation_result.append(vdict)
            results["validation_result"] = validation_result
            # Save after every patch so progress is not lost on a crash
            with open(validation_result_file, "w") as f:
                json.dump(results, f, indent=4)

    # Restore the original buggy file so the next vulnerability starts clean
    with open(buggy_file_path, "w", encoding="utf-8", errors="ignore") as f:
        f.writelines(lines)


if __name__ == '__main__':
    output_dir = os.path.join(ROOT_PATH, 'Model_patches', 'model_output', 'Qwen3')

    # Run validation for each of the 4 transformation types
    for trans in ["rename+code_structure", "original", "structure_change_only", "rename_only"]:
        output_file = os.path.join(output_dir, f'output-{MODEL_NAME}-{trans}.json')
        if not os.path.exists(output_file):
            print(f'Skipping {trans} — output file not found')
            continue
        with open(output_file, "r") as f:
            qwen3_result = json.load(f)
        # Validate every VJBench vulnerability for this transformation
        for vul_id in cve_name_to_int:
            validate_qwen3_vjbench(vul_id, trans, qwen3_result, output_file)
        print(f'Validation finished for {trans}')
