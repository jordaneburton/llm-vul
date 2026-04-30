import os
import json
import sys
from pathlib import Path

PHI4_DIR = os.path.dirname(os.path.abspath(__file__)) + os.sep

sys.path.insert(1, PHI4_DIR + '../')  # utils file
from util import vjbench_bug_id_list, vul4j_bug_id_list

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

this_max_new_tokens = 512
bug_range_list = vjbench_bug_id_list + vul4j_bug_id_list

def generate_phi4_output(input_file, output_file, model_dir, model_name, num_output=10):
    tokenizer = AutoTokenizer.from_pretrained(os.path.join(model_dir, model_name))
    model = AutoModelForCausalLM.from_pretrained(os.path.join(model_dir, model_name)).to('cuda')

    phi4_output = json.load(open(input_file, 'r'))
    phi4_output['model'] = model_name
    for filename in phi4_output['data']:
        text = phi4_output['data'][filename]['input']
        print('generating', filename)
        input_ids = tokenizer(text, return_tensors="pt").input_ids.to('cuda')
        try:
            generated_ids = model.generate(
                input_ids, max_new_tokens=this_max_new_tokens, num_beams=num_output, num_return_sequences=num_output, early_stopping=True
            )
            output = [tokenizer.decode(generated_id, skip_special_tokens=True) for generated_id in generated_ids]
            phi4_output['data'][filename]['output'] = output
        except Exception as e:
            print(e)
            continue
    json.dump(phi4_output, open(output_file, 'w'), indent=2)

if __name__ == '__main__':
    model_dir = "models/microsoft/Phi-4-mini-reasoning"
    for trans in ["structure_change_only", "rename_only", "rename+code_structure", "original"]:
        input_file = os.path.join(PHI4_DIR, "inputs", "input-{}.json".format(trans))
        output_dir = os.path.join(PHI4_DIR, "outputs")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_file = os.path.join(output_dir, "output-phi4-{}.json".format(trans))
        generate_phi4_output(input_file, output_file, model_dir, "Phi-4-mini-reasoning", num_output=10)