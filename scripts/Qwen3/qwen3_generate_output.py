import os
import json
import sys
import re
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Add the scripts/ directory to the path so we can import util.py
QWEN3_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep
sys.path.insert(1, QWEN3_DIR + '../')
from util import ROOT_PATH

# Name of the model folder inside the models/ directory
MODEL_NAME = 'Qwen3-4B'
# How many patch candidates to generate per vulnerability
NUM_OUTPUTS = 10
# Maximum number of new tokens Qwen3 can generate per response
MAX_NEW_TOKENS = 256


def parse_plbart_input(plbart_input_str):
    # The PLBART input format is: <s> code_before </s> buggy_line </s> code_after </s> java
    # Split on the separator token to extract the three parts
    parts = plbart_input_str.split(' </s> ')
    before = parts[0].replace('<s> ', '').strip() if len(parts) > 0 else ''
    buggy_line = parts[1].strip() if len(parts) > 1 else ''
    # Remove the trailing language tag from the after section
    after = parts[2].replace(' </s> java', '').replace('</s> java', '').strip() if len(parts) > 2 else ''
    return before, buggy_line, after


def make_prompt(before, buggy_line, after):
    # Build a natural language instruction prompt for Qwen3.
    # We tell it to return only the fixed line with no explanation
    # to keep the output clean for compilation.
    return (
        "You are a Java security vulnerability fix expert.\n"
        "Fix the buggy line in the Java code below.\n"
        "Reply with only the fixed line(s), no explanation.\n\n"
        f"Code before buggy line:\n{before}\n\n"
        f"Buggy line:\n{buggy_line}\n\n"
        f"Code after buggy line:\n{after}"
    )


def generate_outputs(input_file, output_file, model, tokenizer, device):
    # Load the input JSON which contains buggy code for each vulnerability
    data = json.load(open(input_file, 'r'))
    result = {'model': MODEL_NAME, 'data': {}}

    for vul_id, entry in data['data'].items():
        print(f'generating {vul_id}')

        # Parse the PLBART-formatted input into its three code sections
        before, buggy_line, after = parse_plbart_input(entry['input'])

        # Build the instruction prompt and apply Qwen3's chat template
        # which wraps it in the correct <|im_start|>user ... <|im_end|> format
        prompt = make_prompt(before, buggy_line, after)
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        # Tokenize and move to GPU
        inputs = tokenizer([text], return_tensors="pt").to(f'cuda:{device}')

        outputs = []
        try:
            # Generate NUM_OUTPUTS independent patch candidates using sampling.
            # do_sample=True with temperature/top_p gives diverse outputs
            # rather than always producing the same deterministic result.
            for _ in range(NUM_OUTPUTS):
                with torch.no_grad():
                    generated_ids = model.generate(
                        **inputs,
                        max_new_tokens=MAX_NEW_TOKENS,
                        do_sample=True,
                        temperature=0.7,  # controls randomness (lower = more focused)
                        top_p=0.9,        # nucleus sampling: consider top 90% probability mass
                    )
                # Slice off the input tokens to get only the newly generated tokens
                out_ids = generated_ids[0][inputs.input_ids.shape[1]:]
                raw = tokenizer.decode(out_ids, skip_special_tokens=True)
                # Qwen3 uses chain-of-thought reasoning wrapped in <think> tags.
                # Strip it out so only the actual code fix remains.
                raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
                outputs.append(raw)
        except Exception as e:
            print(f'ERROR on {vul_id}: {e}')
            continue

        # Save this vulnerability's patches to the result and write to disk
        # after each vulnerability so progress is not lost if the script crashes
        result['data'][vul_id] = {
            'loc': entry['loc'],       # line number location of the bug
            'input': entry['input'],   # original PLBART-format input
            'output': outputs,         # list of 10 generated patch candidates
        }
        json.dump(result, open(output_file, 'w'), indent=2)
        print(f'{vul_id} done')


if __name__ == '__main__':
    # First argument is the path to the models/ directory
    model_dir = sys.argv[1]
    device = 0  # GPU index (0 = first GPU)

    # Load the tokenizer and model from the local folder
    model_path = os.path.join(model_dir, MODEL_NAME)
    print(f'Loading tokenizer from {model_path}')
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    print('Loading model...')
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,  # use float16 to halve GPU memory usage
    ).to(device)
    model.eval()  # disable dropout and other training-only behaviour

    # Reuse the input files already generated by the PLBART prepare script
    plbart_input_dir = os.path.join(ROOT_PATH, 'scripts', 'fine-tuned_PLBART', 'inputs')
    output_dir = os.path.join(ROOT_PATH, 'Model_patches', 'model_output', 'Qwen3')
    os.makedirs(output_dir, exist_ok=True)

    # Run generation for each of the 4 code transformation types
    for trans in ["structure_change_only", "rename_only", "rename+code_structure", "original"]:
        input_file = os.path.join(plbart_input_dir, f'input-{trans}.json')
        output_file = os.path.join(output_dir, f'output-{MODEL_NAME}-{trans}.json')
        print(f'\n=== Transformation: {trans} ===')
        generate_outputs(input_file, output_file, model, tokenizer, device)
        print(f'Finished {trans}')
