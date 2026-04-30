import os
import json
import subprocess
import sys
import re

GEMMA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep
sys.path.insert(1, GEMMA_DIR + "../")

from util import cve_test_java_file, cve_compile_java_file, VJBENCH_DIR, info_json, vjbench_json, ROOT_PATH
from util import extract_correct_method_code, translate_code, cve_name_to_int

validation_folder = os.path.join(ROOT_PATH, "Model_patches", "validation", "gemma_vjbench")
os.makedirs(validation_folder, exist_ok=True)


def gemma_output_to_patch(output):
    return output.strip()


def validate_gemma_vjbench(vul_id, trans, gemma_result, gemma_output_file):
    if isinstance(vul_id, str):
        raw_vul_id = "VUL4J-{}".format(cve_name_to_int[vul_id])
    else:
        print("Please input a valid VJBench Bug ID")
        return

    with open(info_json, "r") as f:
        all_info_list = json.load(f)

    for info in all_info_list:
        if info["vul_id"] == raw_vul_id:
            buggy_file_path = info["buggy_file"]
            buggy_method_start = info["buggy_method_with_comment"][0][0]
            buggy_method_end = info["buggy_method_with_comment"][0][1]

            project_path = os.path.join(VJBENCH_DIR, vul_id)
            buggy_file_path = os.path.join(project_path, buggy_file_path)

            with open(vjbench_json, "r") as f:
                vjbench_info = json.load(f)

            compile_cmd = vjbench_info[vul_id]["compile_cmd"]
            test_cmd = vjbench_info[vul_id]["test_cmd"]
            restore_cmd = "git checkout HEAD {}".format(vjbench_info[vul_id]["buggy_file_path"])
            p = subprocess.Popen(restore_cmd.split(), cwd=project_path, stdout=subprocess.PIPE)
            p.wait()
            break

    with open(buggy_file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    if vul_id not in gemma_result["data"]:
        return
    results = gemma_result["data"][vul_id]
    if "output" not in results:
        return
    outputs = results["output"]

    code_before, code_after, flag = extract_correct_method_code(vul_id, trans)
    if not flag:
        return

    validation_result = []
    validation_result_file_name = "{}_{}.json".format(os.path.basename(gemma_output_file)[:-5], vul_id)
    validation_result_file = os.path.join(validation_folder, validation_result_file_name)

    existing_validation_result_length = -1
    if os.path.exists(validation_result_file):
        with open(validation_result_file, "r") as f:
            existing_validation_result = json.load(f)["validation_result"]
            existing_validation_result_length = len(existing_validation_result)
            validation_result = existing_validation_result

    for i in range(len(outputs)):
        if i < existing_validation_result_length:
            continue

        generated_code = gemma_output_to_patch(outputs[i])
        vdict = {"patch": generated_code, "correctness": ""}
        duplicated = False
        check_duplicated = re.sub(r"\s+", "", generated_code).strip()

        for v in validation_result:
            check_v = re.sub(r"\s+", "", v["patch"]).strip()
            if check_duplicated == check_v:
                duplicated = True
                vdict["correctness"] = v["correctness"]
                if trans not in ["original", "structure_change_only"] and "translated" in v:
                    vdict["translated"] = v["translated"]
                validation_result.append(vdict)
                results["validation_result"] = validation_result
                gemma_result["data"][vul_id] = results
                with open(validation_result_file, "w") as f:
                    json.dump(gemma_result["data"][vul_id], f, indent=4)
                print("duplicated")
                break

        if not duplicated:
            if trans not in ["original", "structure_change_only"]:
                generated_code = translate_code(generated_code, vul_id)
                vdict["translated"] = generated_code

            with open(buggy_file_path, "w", encoding="utf-8", errors="ignore") as f:
                f.writelines(lines[:buggy_method_start - 1])
                f.writelines(code_before)
                f.write(generated_code)
                f.writelines(code_after)
                f.writelines(lines[buggy_method_end:])

            print("validation: start compiling")
            if not cve_compile_java_file(project_path, compile_cmd):
                print("validation: compile failed")
                vdict["correctness"] = "uncompilable"
            else:
                vdict["correctness"] = "compile_success"
                print("validation: start testing")
                test_result_value = cve_test_java_file(project_path, test_cmd)
                if test_result_value == 1:
                    print("validation: test success")
                    vdict["correctness"] = "test_success"
                elif test_result_value == 2:
                    print("test_timeout")
                    vdict["correctness"] = "test_timeout"

            validation_result.append(vdict)
            results["validation_result"] = validation_result
            gemma_result["data"][vul_id] = results
            with open(validation_result_file, "w") as f:
                json.dump(gemma_result["data"][vul_id], f, indent=4)

    with open(buggy_file_path, "w", encoding="utf-8", errors="ignore") as f:
        f.writelines(lines)


if __name__ == "__main__":
    model_name = "gemma-4-E4B-it"
    for trans in ["rename+code_structure", "original", "structure_change_only", "rename_only"]:
        gemma_output_file = os.path.join(
            ROOT_PATH, "Model_patches", "model_output", "Gemma",
            "output-{}-{}.json".format(model_name, trans)
        )
        with open(gemma_output_file, "r") as f:
            gemma_result = json.load(f)

        for vul_id in cve_name_to_int:
            validate_gemma_vjbench(vul_id, trans, gemma_result, gemma_output_file)

        print("Validation finished for", trans)
