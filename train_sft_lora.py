from datasets import load_from_disk
from transformers import (AutoModelForCausalLM, AutoTokenizer, TrainingArguments,
                          BitsAndBytesConfig)
from trl import SFTTrainer
from peft import LoraConfig, get_peft_model

MODEL_NAME = "meta-llama/Llama-4-Scout-17B-16E-Instruct"  # or Llama-3.1-8B-Instruct
DATA_DIR = "paladin_sft_ds"
OUT_DIR = "paladin-lora-sft"
USE_4BIT = True  # QLoRA

# 1) Tokenizer
tok = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

# 2) Quantization (QLoRA)
quant = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype="bfloat16",
) if USE_4BIT else None

# 3) Base model
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME, device_map="auto", torch_dtype="bfloat16",
    quantization_config=quant, trust_remote_code=True,
)

# 4) LoRA setup (targets standard attention/MLP proj layers)
lora_cfg = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05, bias="none",
           task_type="CAUSAL_LM",
           target_modules=["q_proj","k_proj","v_proj","o_proj","up_proj","down_proj","gate_proj"])
)
model = get_peft_model(model, lora_cfg)

# 5) Dataset
train_ds = load_from_disk(DATA_DIR)

# 6) Trainer
args = TrainingArguments(
    output_dir=OUT_DIR,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,     # raise on bigger GPUs
    num_train_epochs=1.0,              # start small; scale later
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    logging_steps=10,
    save_steps=200,
    save_total_limit=2,
    bf16=True,
    gradient_checkpointing=True,
    optim="paged_adamw_32bit"          # good for QLoRA
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tok,
    train_dataset=train_ds,
    dataset_text_field="text",
    max_seq_length=4096,       # bump if your context is longer
    packing=True,              # efficient packing of short chats
    args=args,
)
trainer.train()
trainer.save_model(OUT_DIR)
tok.save_pretrained(OUT_DIR)
