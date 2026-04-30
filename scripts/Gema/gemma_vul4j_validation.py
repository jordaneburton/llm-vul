import os
import json
import sys
import re
import multiprocessing

GEMMA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep
sys.path.insert(1, GEMMA_DIR + "../")

from util import vul4j_compile_java_file, vul4j_test_java_file, vul4j_bug_id_list, ROOT_PATH, info_json, VUL4J_DIR
from util import extract_correct_method_code, translate_code

validation_folder = os.path.join(ROOT_PATH, "Model_patches", "validation", "gemma_vul4j")
os.makedirs(validation_folder, exist_ok=True)


def gemma_output_to_patch(output):
    return output.strip()


def validate_gemma_vul4j(vul_id_int):
    raw_vul_id = "VUL4J-{}".format(vul_id_int)
    vul4j_project_path = os.path.join(VUL4J_DIR, raw_vul_id)

    with open(info_json, "r") as f:
        all_info_list = json.load(f)

    for info in all_info_list:
        if info["vul_id"] == raw_vul_id:
            compile_cmd = "vul4j compile -d {}".format(vul4j_project_path)
            test_cmd = "vul4j test -d {}".format(vul4j_project_path)
            if "buggy_file" not in info:
                print("{} buggy file not exist".format(vul_id_int))
                return

            buggy_file_path = os.path.join(vul4j_project_path, info["buggy_file"])
            buggy_method_start = info["buggy_method_with_comment"][0][0]
            buggy_method_end = info["buggy_method_with_comment"][0][1]
            original_file_path = os.path.join(vul4j_project_path, "VUL4J", "original_whole_file.txt")
            print("successfully get the info")
            break

    with open(original_file_path, "r") as f:
        lines = f.readlines()

    validation_result = []
    code_before, code_after, flag = extract_correct_method_code(raw_vul_id, trans)
    if not flag:
        return

    vul_id = raw_vul_id
    if vul_id not in gemma_result["data"]:
        return
    results = gemma_result["data"][vul_id]
    if "output" not in results:
        return
    outputs = results["output"]

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
                generated_code = translate_code(generated_code, vul_id_int)
                vdict["translated"] = generated_code

            with open(buggy_file_path, "w") as f:
                f.writelines(lines[:buggy_method_start - 1])
                f.writelines(code_before)
                f.write(generated_code)
                f.writelines(code_after)
                f.writelines(lines[buggy_method_end:])

            print("validation: start compiling")
            if not vul4j_compile_java_file(vul4j_project_path, compile_cmd):
                print("validation: compile failed")
                vdict["correctness"] = "uncompilable"
            else:
                vdict["correctness"] = "compile_success"
                print("validation: start testing")
                test_result_value = vul4j_test_java_file(vul4j_project_path, test_cmd)
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

    with open(buggy_file_path, "w") as f:
        f.writelines(lines)


if __name__ == "__main__":
    model_name = "gemma-4-E4B-it"
    for trans in ["original", "rename+code_structure", "structure_change_only", "rename_only"]:
        gemma_output_file = os.path.join(
            ROOT_PATH, "Model_patches", "model_output", "Gemma",
            "output-{}-{}.json".format(model_name, trans)
        )
        with open(gemma_output_file, "r") as f:
            gemma_result = json.load(f)

        p = multiprocessing.Pool(1)
        p.map(validate_gemma_vul4j, vul4j_bug_id_list)
        print("Validation finished for", trans)
