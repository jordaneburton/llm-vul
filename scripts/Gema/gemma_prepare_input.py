import os
import json
import sys

GEMMA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep
sys.path.insert(1, GEMMA_DIR + "../")

from util import dedent_the_whole_method, vjbench_bug_id_list, vul4j_bug_id_list, cve_int_to_name

bug_range_list = vjbench_bug_id_list + vul4j_bug_id_list
with_comment = False


def generate_gemma_input(output_file, trans):
    gemma_input = {"config": comment_config, "data": {}}
    for vul_int in bug_range_list:
        vul_id = "VUL4J-{}".format(vul_int)
        if vul_int > 1000:
            vul_id = cve_int_to_name[vul_int]

        vul_folder = os.path.join(GEMMA_DIR + "../../VJBench-trans", vul_id)
        bug_location_file = os.path.join(vul_folder, "buggyline_location.json")
        if not os.path.exists(bug_location_file):
            continue

        with open(bug_location_file, "r") as f:
            buggy_line_dict = json.load(f)

        buggy_line_list = buggy_line_dict[trans]

        if trans == "structure_change_only":
            buggy_file = os.path.join(vul_folder, "{}_code_structure_change_only.java".format(vul_id))
        elif trans == "rename+code_structure":
            buggy_file = os.path.join(vul_folder, "{}_full_transformation.java".format(vul_id))
        elif trans == "rename_only":
            buggy_file = os.path.join(vul_folder, "{}_rename_only.java".format(vul_id))
        else:
            buggy_file = os.path.join(vul_folder, "{}_original_method.java".format(vul_id))

        if not os.path.exists(buggy_file):
            continue

        buggy_line_start = buggy_line_list[0][0]
        buggy_line_end = buggy_line_start if len(buggy_line_list[0]) == 1 else buggy_line_list[0][1]

        with open(buggy_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        buggy_method_start = 1
        buggy_method_end = len(lines)
        buggy_lines = lines[buggy_method_start - 1 : buggy_method_end]

        min_indent_len = 1000000
        for i in range(buggy_line_start - 1, buggy_line_end):
            this_line = lines[i]
            j = 0
            while j < len(this_line) and len(this_line[j].strip()) == 0:
                j += 1
            if j < min_indent_len:
                min_indent_len = j

        new_buggy_line_list = []
        for k in range(0, buggy_line_start - buggy_method_start):
            new_buggy_line_list.append(buggy_lines[k])

        if with_comment:
            new_buggy_line_list.append(
                buggy_lines[buggy_line_start - buggy_method_start][:min_indent_len] + "/* BUG: \n"
            )
            for k in range(buggy_line_start - buggy_method_start, buggy_line_end - buggy_method_start + 1):
                new_buggy_line_list.append(
                    buggy_lines[k][:min_indent_len] + " * " + buggy_lines[k][min_indent_len:]
                )
            new_buggy_line_list.append(
                buggy_lines[buggy_line_start - buggy_method_start][:min_indent_len] + " * FIXED: \n"
            )
            new_buggy_line_list.append(
                buggy_lines[buggy_line_start - buggy_method_start][:min_indent_len] + " */\n"
            )

        suffix = []
        for k in range(buggy_line_end - buggy_method_start + 1, len(buggy_lines)):
            suffix.append(buggy_lines[k])

        d_input, d_suffix = dedent_the_whole_method(new_buggy_line_list, suffix)
        prefix_prompt = "".join(d_input)
        suffix_prompt = "".join(d_suffix)

        gemma_input["data"][vul_id] = {
            "input": prefix_prompt
        }

        with open(output_file, "w") as f:
            json.dump(gemma_input, f, indent=2)


if __name__ == "__main__":
    for trans in ["structure_change_only", "rename_only", "rename+code_structure", "original"]:
        comment_config = "WITH_COMMENT" if with_comment else "NO_COMMENT"
        input_folder = os.path.join(GEMMA_DIR, "inputs")
        os.makedirs(input_folder, exist_ok=True)
        input_file = os.path.join(input_folder, "input-{}.json".format(trans))
        generate_gemma_input(input_file, trans)
