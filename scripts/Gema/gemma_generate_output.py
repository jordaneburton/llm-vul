import os
import json
import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

GEMMA_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep
sys.path.insert(1, GEMMA_DIR + "../")

this_max_new_tokens = 512


def build_prompt(code_snippet: str) -> str:
    return (
        "You are a Java vulnerability repair assistant.\n"
        "Given buggy Java method context, generate only the fixed Java method code.\n\n"
        + code_snippet
    )


def generate_gemma_output(input_file, output_file, model_dir, model_name, num_output=10):
    model_path = os.path.join(model_dir, model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype="auto",
        device_map="auto"
    )

    gemma_output = json.load(open(input_file, "r"))
    gemma_output["model"] = model_name

    if os.path.exists(output_file):
        gemma_output = json.load(open(output_file, "r"))

    for filename in gemma_output["data"]:
        if "output" in gemma_output["data"][filename]:
            continue

        text = gemma_output["data"][filename]["input"]
        prompt = build_prompt(text)
        print("generating", filename)

        messages = [{"role": "user", "content": prompt}]
        model_input = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        ).to(model.device)

        try:
            generated = model.generate(
                model_input,
                max_new_tokens=this_max_new_tokens,
                do_sample=False,
                num_beams=num_output,
                num_return_sequences=num_output
            )
            output = [tokenizer.decode(g, skip_special_tokens=True) for g in generated]
        except Exception as e:
            print("Exception:", e)
            continue

        gemma_output["data"][filename]["output"] = output
        json.dump(gemma_output, open(output_file, "w"), indent=2)


if __name__ == "__main__":
    model_dir = sys.argv[1]
    model_name = "gemma-4-E4B-it"

    for trans in ["structure_change_only", "rename_only", "rename+code_structure", "original"]:
        input_file = os.path.join(GEMMA_DIR, "inputs", "input-{}.json".format(trans))
        output_dir = os.path.join(GEMMA_DIR, "outputs")
        os.makedirs(output_dir, exist_ok=True)

        tmp_output_file = os.path.join(
            output_dir,
            "output-{}-max_new_tokens-{}-{}.json".format(model_name, this_max_new_tokens, trans)
        )
        generate_gemma_output(input_file, tmp_output_file, model_dir, model_name, num_output=10)

        final_dir = os.path.join(GEMMA_DIR, "../../Model_patches/model_output/Gemma")
        os.makedirs(final_dir, exist_ok=True)
        final_file = os.path.join(final_dir, "output-{}-{}.json".format(model_name, trans))

        with open(tmp_output_file, "r") as src, open(final_file, "w") as dst:
            dst.write(src.read())

