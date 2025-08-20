import json
from datasets import Dataset
from transformers import AutoTokenizer

DATA_PATH = "/workspace/data/paladin.jsonl"
MODEL_NAME = "meta-llama/Llama-4-Scout-17B-16E-Instruct"  # or "meta-llama/Llama-3.1-8B-Instruct"

def stream_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if line:
                yield json.loads(line)

def to_chat_msgs(row):
    msgs = []
    for t in row.get("conversations", []):
        role = (t.get("from","").lower())
        text = t.get("value","")
        if role in ("user", "human"):
            msgs.append({"role":"user","content":text})
        elif role in ("assistant", "gpt"):
            msgs.append({"role":"assistant","content":text})
        elif role == "system":
            msgs.append({"role":"system","content":text})
        elif role in ("function","tool"):
            # Keep tool traces so PALADIN learns recovery patterns
            msgs.append({"role":"assistant","content":f"<tool_output>\n{text}\n</tool_output>"})
        else:
            msgs.append({"role":"system","content":text})
    return msgs

def main():
    tok = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True, trust_remote_code=True)
    data = []
    for row in stream_jsonl(DATA_PATH):
        chat = to_chat_msgs(row)
        if not chat: 
            continue
        text = tok.apply_chat_template(chat, tokenize=False, add_generation_prompt=False)
        data.append({"text": text})
    ds = Dataset.from_list(data)
    ds.save_to_disk("paladin_sft_ds")

if __name__ == "__main__":
    main()
