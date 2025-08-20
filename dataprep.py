import json
from datasets import Dataset
from typing import List, Dict
from transformers import AutoTokenizer

DATA_PATH = "/mnt/data/Sampleofourdata.jsonl"
MODEL_NAME = "meta-llama/Meta-Llama-3.1-8B-Instruct"  # or "Qwen/Qwen2.5-7B-Instruct"

def load_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def to_chat_messages(sample: Dict) -> List[Dict[str, str]]:
    """Convert your ToolBench-like structure into HF chat messages.

    Expected: sample["conversations"] = [{"from": "...", "value": "..."}, ...]
    Map:
      - user  -> "user"
      - assistant -> "assistant"
      - system (if present) -> "system"
      - tool/function -> wrap as assistant/tool or skip
    """
    msgs = []
    for turn in sample.get("conversations", []):
        role = turn.get("from", "").lower()
        text = turn.get("value", "")

        if role in ("user", "human"):
            msgs.append({"role": "user", "content": text})
        elif role in ("assistant", "gpt"):
            msgs.append({"role": "assistant", "content": text})
        elif role in ("system"):
            msgs.append({"role": "system", "content": text})
        elif role in ("function", "tool"):
            # Option A: keep as assistant content with tags (teaches tool traces)
            msgs.append({"role": "assistant", "content": f"<tool_output>\n{text}\n</tool_output>"})
            # Option B: comment previous line & skip tools if you don’t want to train on them.
        else:
            # Unknown role → treat as system note
            msgs.append({"role": "system", "content": text})
    return msgs

def main():
    tk = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True, trust_remote_code=True)

    texts = []
    for row in load_jsonl(DATA_PATH):
        chat = to_chat_messages(row)
        if not chat:
            continue
        # Convert chat messages to final string with model’s chat template
        text = tk.apply_chat_template(
            chat,
            tokenize=False,
            add_generation_prompt=False  # We train on full dialogues including assistant outputs
        )
        texts.append({"text": text})

    ds = Dataset.from_list(texts)
    ds.save_to_disk("paladin_sft_dataset")  # fast reload later

if __name__ == "__main__":
    main()
