"""
PALADIN - LoRA Fine-Tuning Example
----------------------------------
This simplified script demonstrates how PALADIN models were fine-tuned using
Supervised Fine-Tuning (SFT) with a QLoRA adapter.

It mirrors the training logic described in the paper:
- Uses a chat-style dataset (PALADIN conversation format)
- Applies a consistent system/user/assistant template
- Trains a lightweight LoRA adapter on top of an instruction-tuned base model

This version is minimal, fully reproducible, and CPU/GPU friendly.
"""

import os
import json
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model

# --- Config ---
MODEL_ID = os.getenv("MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
DATA_PATH = os.getenv("DATA_PATH", "data/paladin_train_demo.jsonl")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "checkpoints/paladin_demo")
MAX_LENGTH = 2048

# --- Load Tokenizer + Model ---
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(MODEL_ID)

# --- Apply LoRA (PEFT) Adapter ---
peft_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    target_modules=["q_proj", "v_proj"],
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, peft_config)

# --- Load Dataset ---
ds = load_dataset("json", data_files=DATA_PATH, split="train")

def to_chat_text(example):
    """Flatten messages → one string while tracking char spans by role."""
    msgs = example.get("messages") or example.get("conversations") or []
    parts, spans = [], []
    cursor = 0
    for m in msgs:
        role = m.get("role", m.get("from", "user"))
        value = m.get("content", m.get("value", ""))
        if isinstance(value, list):
            value = "\n".join(str(v.get("text", v)) for v in value)
        # Standardize role headers so masking is easy to read/debug (optional)
        block = f"{role.upper()}:\n{value}\n"
        start, end = cursor, cursor + len(block)
        parts.append(block)
        spans.append({"role": role.lower(), "start": start, "end": end})
        cursor = end
    return {"text": "".join(parts), "spans": spans}

ds = ds.map(to_chat_text, remove_columns=ds.column_names)
ds = ds.filter(lambda x: len(x["text"]) > 0)

def tokenize_with_mask(batch):
    enc = tokenizer(
        batch["text"],
        truncation=True,
        max_length=MAX_LENGTH,
        padding="max_length",
        return_offsets_mapping=True,   # <— needed to map chars→tokens
    )
    labels = []
    for i in range(len(batch["text"])):
        offs = enc["offset_mapping"][i]
        # Build an initial mask: default -100 (ignored)
        lab = [-100] * len(offs)

        # Mark tokens that fall inside ASSISTANT spans as learnable
        for span in batch["spans"][i]:
            if span["role"] in ("assistant",):  # add "assistant"
                s, e = span["start"], span["end"]
                for tidx, (a, b) in enumerate(offs):
                    # skip special tokens with (0,0) or (-1,-1)
                    if a == b == 0 and tokenizer.convert_ids_to_tokens(enc["input_ids"][i][tidx]).startswith(tokenizer.special_tokens_map.get("pad_token", "")):
                        continue
                    # token overlaps assistant char span?
                    if (a < e) and (b > s):
                        # supervise this token
                        lab[tidx] = enc["input_ids"][i][tidx]

        labels.append(lab)

    # strip offset mappings for Trainer
    enc.pop("offset_mapping", None)
    enc["labels"] = labels
    return enc

tokenized_ds = ds.map(tokenize_with_mask, batched=False, remove_columns=["text", "spans"])

# --- Collator ---
collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

# --- Training Setup ---
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    num_train_epochs=1,
    logging_steps=10,
    save_steps=50,
    save_total_limit=1,
    bf16=False,  # enable if available
    fp16=False,
)

# --- Trainer ---
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_ds,
    data_collator=collator,
)

trainer.train()

# --- Save Adapter ---
model.save_pretrained(f"{OUTPUT_DIR}/adapter")
tokenizer.save_pretrained(f"{OUTPUT_DIR}/adapter")
print("PALADIN adapter saved to", f"{OUTPUT_DIR}/adapter")
