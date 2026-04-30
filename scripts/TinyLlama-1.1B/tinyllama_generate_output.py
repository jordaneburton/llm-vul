import os
import json
import sys
from pathlib import Path

TINYLLAMA_DIR = os.path.abspath(__file__)[: os.path.abspath(__file__).rindex('/') + 1]

sys.path.insert(1, TINYLLAMA_DIR+'../') # utils file
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

this_max_new_tokens = 512

def generate_tinyllama_output(input_file, output_file, model_dir, model_name, device, num_output=10):
    # Load TinyLlama model and tokenizer
    tokenizer = AutoTokenizer.from_pretrained(os.path.join(model_dir, model_name))
    model = AutoModelForCausalLM.from_pretrained(os.path.join(model_dir, model_name)).to(device)
    
    # Set padding token if not set
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    tinyllama_output = json.load(open(input_file, 'r'))
    tinyllama_output['model'] = model_name
    for filename in tinyllama_output['data']:
        text = tinyllama_output['data'][filename]['input']

        print('generating', filename)

        # Prepare input with chat template
        # For TinyLlama, we use a simple instruction format
        prompt = f"<|system|>\nYou are a code repair assistant. Fix the vulnerable code.</s>\n<|user|>\n{text}</s>\n<|assistant|>\n"
        
        input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to(device)
        eos_id = tokenizer.eos_token_id
        
        try:
            generated_ids = model.generate(
                input_ids, 
                max_new_tokens=this_max_new_tokens, 
                num_beams=num_output, 
                num_return_sequences=num_output, 
                early_stopping=True, 
                pad_token_id=tokenizer.pad_token_id, 
                eos_token_id=eos_id
            )
        except Exception as e:
            print(e)
            continue
        
        output = []
        for generated_id in generated_ids:
            # Decode and remove the prompt from the output
            full_output = tokenizer.decode(generated_id, skip_special_tokens=False)
            # Try to extract only the generated part after the assistant token
            if "<|assistant|>" in full_output:
                generated_part = full_output.split("<|assistant|>")[-1]
                output.append(generated_part)
            else:
                output.append(tokenizer.decode(generated_id, skip_special_tokens=True))
        
        tinyllama_output['data'][filename]['output'] = output
        json.dump(tinyllama_output, open(output_file, 'w'), indent=2)



# main funtion:
if __name__ == '__main__':
    model_dir = sys.argv[1]
    for trans in [
            "structure_change_only", 
            "rename_only", 
            "rename+code_structure",
            "original"]:
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        input_file = os.path.join(TINYLLAMA_DIR,"inputs","input-{}.json".format(trans))
        output_dir = os.path.join(TINYLLAMA_DIR,"outputs")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        for model_name in ["TinyLlama-1.1B-Chat-v1.0"]:
            output_file = os.path.join(output_dir,"output-{}-max_new_tokens-{}-{}.json".format(model_name, this_max_new_tokens, trans))
            generate_tinyllama_output(input_file, output_file, model_dir, model_name, device, num_output=10)
