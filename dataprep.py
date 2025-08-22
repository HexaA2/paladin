import json
import os
from datasets import Dataset
from transformers import AutoTokenizer, LlamaForCausalLM, Trainer, TrainingArguments

# Paths
DATA_PATH = "/workspace/data/puretraining.jsonl"
MODEL_NAME = "meta-llama/Llama-4-Scout-17B-16E-Instruct"
OUTPUT_DIR = "./llama4_finetuned"

# Load tokenizer and model
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True, trust_remote_code=True)
model = LlamaForCausalLM.from_pretrained(MODEL_NAME)

# Stream JSONL data
def stream_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

# Convert row to chat messages
def to_chat_msgs(row):
    msgs = []
    for t in row.get("conversations", []):
        role = t.get("from", "").lower()
        text = t.get("value", "")
        if role in ("user", "human"):
            msgs.append({"role": "user", "content": text})
        elif role in ("assistant", "gpt"):
            msgs.append({"role": "assistant", "content": text})
        elif role == "system":
            msgs.append({"role": "system", "content": text})
        elif role in ("function", "tool"):
            msgs.append({"role": "assistant", "content": f"<tool_output>\n{text}\n</tool_output>"})
        else:
            msgs.append({"role": "system", "content": text})
    return msgs

# Prepare dataset
def prepare_dataset():
    data = []
    for row in stream_jsonl(DATA_PATH):
        chat = to_chat_msgs(row)
        if not chat:
            continue
        text = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=False)
        data.append({"text": text})
    return Dataset.from_list(data)

# Tokenize dataset
def tokenize_function(examples):
    return tokenizer(examples["text"], padding="max_length", truncation=True, max_length=2048)

# Main function
def main():
    dataset = prepare_dataset()
    tokenized_dataset = dataset.map(tokenize_function, batched=True)

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        evaluation_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        num_train_epochs=3,
        weight_decay=0.01,
        logging_dir="./logs",
        logging_steps=10,
        save_steps=500,
        save_total_limit=2,
        fp16=True,
        gradient_checkpointing=True,
        optim="adamw_torch",
        lr_scheduler_type="linear",
        report_to="tensorboard",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        eval_dataset=tokenized_dataset,
        tokenizer=tokenizer,
    )

    trainer.train()
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

if __name__ == "__main__":
    main()
