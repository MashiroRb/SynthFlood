"""Infrastructure smoke check only; no experimental or exam prompts."""
import os
import torch
import vllm
from vllm import LLM, SamplingParams

if __name__=='__main__':
    model='/mnt/beegfs/home/liudianru26/.cache/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28'
    print('VERSIONS',torch.__version__,vllm.__version__,'GPU',torch.cuda.get_device_name(0),flush=True)
    llm=LLM(model=model,dtype='bfloat16',max_model_len=8192,max_num_seqs=1,
            enforce_eager=True,gpu_memory_utilization=.88,seed=2027,
            enable_prefix_caching=False,max_num_batched_tokens=8192)
    prompt=llm.get_tokenizer().apply_chat_template([{'role':'user','content':'Reply with exactly OK.'}],tokenize=False,add_generation_prompt=True)
    outputs=llm.generate([prompt]*3,SamplingParams(temperature=0,max_tokens=8,seed=0))
    replies=[out.outputs[0].text for out in outputs]
    print('PREFLIGHT_REPLIES',replies,flush=True)
    if len(set(replies))!=1:
        raise RuntimeError('Infrastructure repeatability smoke check failed')
    print('GPU_PREFLIGHT_OK',flush=True)
