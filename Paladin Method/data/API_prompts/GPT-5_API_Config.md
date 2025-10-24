### PALADIN GPT-5 Evaluation Configuration

This document specifies the **exact GPT-5 API settings** used in PALADIN’s evaluation pipeline.  
It ensures reviewers can reproduce all reported results from the GPT-5 API using identical model, decoding parameters, and deterministic sampling.  

---

## Model Identifier
model = gpt-5-chat-latest

Rationale:
Deterministic conversational variant of GPT-5 with full reasoning context.
This was the latest stable model from OpenAI at the time of the paper’s creation.

## Temperature / Determinism
temperature = 0.0

Setting temperature = 0.0 ensures the GPT-5 grader behaves deterministically and produces consistent scores across runs.

Note:
For annotation tasks (not grading), a slightly exploratory temperature of 0.2 was used without any fixed seed.

## Max Tokens
max_tokens = 1000

Allows the grader to output a complete JSON artifact for long, multi-turn conversations.

## Seed
seed = 42

Ensures reproducibility across grading runs and aligns with the deterministic configuration described in Eval_Protocol.md.

## Prompt Reference
prompt_path = <prompt-used>.txt

Specifies the location of the grader system prompt that defines the evaluation schema, rules, and restrictions for the task at hand.

Example:
prompt_path = grader_prompt.txt (for evaluation)

## Enviornmental Variables
To run the official grading pipeline:
    export OPENAI_API_KEY="your_api_key_here"
    export USE_API=true
    export EVAL_MODEL=gpt-5-chat-latest
