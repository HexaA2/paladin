# Evaluation Protocol (PALADIN)

This document describes the deterministic evaluation protocol used to score agent performance during tool-use recovery experiments.

_Last updated: October 12, 2025_

---

## 1. Evaluator Configuration

The evaluator (referred to as `grader.py`) follows the definitions provided in [`grader_prompt.txt`](../data/API_prompts/grader_prompt.txt).  
It runs deterministically using the **GPT-5 API** with the following configuration:

- **Model:** `gpt-5-turbo`
- **Temperature:** `0.0` → ensures *deterministic, reproducible scoring*
- **Max tokens:** 4000
- **Top-p:** 1.0  
- **Frequency & presence penalties:** 0  
- **System role:** `"Expert evaluator for tool-augmented language-model agents"`

Each grading run is entirely repeatable. No stochastic sampling is used.

---

## 2. Inputs Provided to the Evaluator

For each conversation file (JSON):

- Original **task prompt**
- Full **list of available tools** (with input/output schemas)
- Full **conversation history**, including:
  - All assistant → tool calls
  - All tool → assistant outputs
  - Injected synthetic or natural **errors**

---

## 3. Deterministic Evaluation Principles

The evaluator adheres to the following mechanical rules:

- Prefer **objective, checkable** criteria.
- Judge **final correctness** separately from **process cleanliness**.
- Never infer facts the tools did not return.
- When uncertain, choose the **conservative** (non-credit) option.

---

## 4. Scoring Metrics

All outputs are returned as a single JSON block per conversation:

```json
{
  "id": <int>,
  "Has_Error": <bool>,

  "TSR": <bool>,
  "Evidence_Match": <bool>,
  "Task_Coverage": <float>,

  "Tool_Cleanliness": <float>,
  "Tool_Calls": <int>,
  "Tool_Errors": <int>,

  "RR_Attempted": <bool>,
  "Distinct_Adaptations": <int>,
  "RR_Success": <bool>,

  "FCR": <bool>,
  "Efficiency": <int>,

  "Finish_Gated": <bool>
}
```

---

### Metric Definitions

| Metric | Type | Description |
|---------|------|--------------|
| **Has_Error** | bool | True if any tool call returned a 4xx/5xx, timeout, or schema violation. |
| **Task Success Rate (TSR)** | bool | True if `Task_Coverage ≥ 0.40` and `Evidence_Match = true`. Partial completions ≥40% count as success. |
| **Evidence Match** | bool | True only if all *delivered* facts are supported by tool evidence. Missing deliverables do not penalize this metric. |
| **Task Coverage** | float [0,1] | (# deliverables correctly satisfied) ÷ (# deliverables requested). |
| **Tool Cleanliness** | float [0,1] | Ratio of valid tool calls; diagnostic only. |
| **Recovery Attempted (RR_Attempted)** | bool | True if agent acknowledges any error and performs a recovery action (parameter fix, schema repair, alternative tool, etc.). |
| **Distinct Adaptations** | int | Count of substantive recovery strategies (e.g., switch tool, reformat payload, retry with different parameters). |
| **Recovery Success (RR_Success)** | bool | True if valid outputs obtained for ≥80% of deliverables after recovery attempts. Graceful acknowledgment of unfixable external errors may count as success per exception rule. |
| **Hallucinated Completion (FCR)** | bool | True only if the final answer is unsupported or contradicts evidence. |
| **Efficiency** | int | Number of valid tool-invoking assistant messages (diagnostic). |
| **Finish_Gated** | bool | True if the final completion is supported by *any* valid tool output in the conversation. |

---

## 5. Relationship to Main Reported Metrics

The PALADIN framework reports **four main quantitative metrics** in the paper:

- **TSR (Task Success Rate)**  
- **RR (Recovery Rate)**  
- **CSR (Cascaded Success Rate) (100%-FCR)**  
- **ES (Efficiency Score)**  

All other metrics in the JSON schema (e.g., `Evidence_Match`, `Tool_Cleanliness`, etc.) are diagnostic — they exist primarily to help the **GPT-5 grader** systematically and deterministically derive these four main metrics without ambiguity.

---

## 6. Deterministic Scoring Order

The grader always follows this order:

1. Compute `Has_Error`
2. Parse all tool calls and index deliverables
3. Compute `Task_Coverage`
4. Compute `Evidence_Match`
5. Compute `Tool_Cleanliness`, `Tool_Calls`, `Tool_Errors`
6. Detect recovery attempts → `RR_Attempted`, `Distinct_Adaptations`
7. Evaluate `RR_Success` using the auto-assertions defined in `newgrader.txt`
8. Infer `TSR` via deterministic rules  
9. Compute `FCR`, `Efficiency`, and `Finish_Gated`
10. Write results to `eval_results.jsonl`

---

## 7. Example Deterministic Runs

- **Example A:** Tool errors followed by recovery → `RR_Success=true`, `TSR=true`.  
- **Example B:** Repeated schema failures with graceful exit → `RR_Success=true`, `TSR=false`.  
- **Example C:** Hallucinated completion with no evidence → `FCR=true`, `TSR=false`.

See `grader_examples/` for detailed input/output pairs.

---

## 8. Reproducibility
- Random seeds are irrelevant because no stochastic sampling occurs.
- Each run yields byte-identical outputs across machines.

---

## 9. Citation

If referencing this evaluation protocol, please cite:

> PALADIN Evaluation Framework (2025).  
> *Deterministic Recovery Grading for Tool-Augmented Language Models.*  
> GitHub: [https://github.com/HexaA2/paladin](https://github.com/HexaA2/paladin)
