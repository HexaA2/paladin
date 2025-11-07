# PALADIN: Self-Correcting Language Model Agents to Cure Tool-Failure Cases
[![Paper](https://img.shields.io/badge/Paper-ICLR_2026-blue)](https://openreview.net/forum?id=M2AXTAKXbz&referrer=%5BAuthor%20Console%5D(%2Fgroup%3Fid%3DICLR.cc%2F2026%2FConference%2FAuthors%23your-submissions)) 
[![Dataset](https://img.shields.io/badge/Dataset-HuggingFace-orange)](https://huggingface.co/datasets/SriVatsa123/Gemma_Ready_For_PALADIN)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Reproducibility](https://img.shields.io/badge/Reproducibility-✓-brightgreen)](#reproducibility-checklist)

---

### Official Implementation of *“PALADIN: Self-Correcting Language Model Agents to Cure Tool-Failure Cases”*  

---
 
## 1. Overview

**PALADIN** is a framework and dataset for building robust, self-recovering tool-using language model agents.
It trains on 50K+ failure-injected, recovery-annotated trajectories to equip LLMs with fault tolerance, recovery reasoning, and resilience against real-world API and tool failures — outperforming CRITIC, ToolReflect, and ToolBench baselines by over +13% in Recovery Rate and +10% in Task Success Rate across Gemma, Qwen, and LLaMA backbones.  

> **Key Idea:** PALADIN treats failures as data.  
> By injecting and labeling diverse tool-level errors, it learns not only to perform tasks but to *self-repair*. 

---

## 2. Repository Structure
```
├── data/
│ ├── API_prompts/
│ │ ├── annotate_clean.txt
│ │ ├── annotate_recovery.txt
│ │ ├── grader_prompt.txt
│ │ ├── simulator_prompt.txt
│ │ └── GPT-5_API_Config.md
│ ├── recovery_dictionary.json
│ ├── toolscan_taxonomy_map.json
│ └── docs/
│ ├── Eval_Protocol_PALADIN.md
│ └── appendix_links.md
│
├── examples/
│ ├── annotation_sample/
│ ├── evaluation_sample/
│ └── ...
│
├── src/paladin/
│ ├── data_creation/
│ ├── error_matching/
│ ├── simulation/
│ ├── evaluation/
│ └── training/
│
├── results/
│ ├── paladin_eval_sample.jsonl
│ └── reference_metrics.md
│
└── figures/
```
---

## 3. Core Components

| Module | Purpose |
|:--|:--|
| `annotate_clean.py` | Repairs truncated or invalid ToolBench traces into clean, complete rollouts. |
| `annotate_recovery.py` | Injects controlled tool errors and synthesizes labeled recovery trajectories. |
| `simulation.py` | Executes multi-turn deterministic simulations between the agent and tools. |
| `simulation_with_paladin_error_match.py` | Adds **error-matching logic** that maps unseen failures to known recovery exemplars. |
| `eval.py` | Grades a full conversation using GPT-5 to compute TSR, RR, CSR, and ES. |
| `train.py` | Simplified LoRA fine-tuning pipeline for recovery-aware SFT. |

---

## 4. Metrics

| Metric | Definition | Description |
|:--|:--|:--|
| **TSR** | `#Successful / #Total` | Overall task completion rate. |
| **RR** | `#Recovered / #Failures` | Ability to repair after an error. |
| **CSR** | `1 - (#Hallucinated_Success / #Failures)` | Penalizes silent failures. |
| **ES** | `1 / Avg_Steps` | Efficiency of reasoning and recovery. |

All metrics are produced by a deterministic GPT-5 grader (`temperature = 0.0`, `seed = 42`) defined in [`GPT-5_API_Config.md`](data/API_prompts/GPT-5_API_Config.md).

---

## 5. Quick Start

### Environment
```bash
git clone https://github.com/HexaA2/paladin.git
cd paladin
pip install -r requirements.txt
export OPENAI_API_KEY="your_api_key_here"
```

---
## 6. Dataset Construction
- Base rollouts from ToolBench
- 7 error categories aligned with ToolScan taxonomy
- Controlled failure injection via annotate_recovery.py
- GPT-5-driven recovery synthesis using recovery_dictionary.json
- 50k+ trajectories combining clean and recovery variants

Huggingface:
https://huggingface.co/datasets/E-k-O/PaladinDataSet
---
## 7. Training Configuration
| Parameter | Setting |
|:--|:--|
| Backbone Models | Gemma-27B, Qwen-14B-Instruct, AM-Thinking-V1, LLaMA-3.1-8B-Instruct |
| Fine-tuning | LoRA rank 16, α = 32, bf16 |
| Dataset Size | 50,000 |
| Objective | `L = L_SFT + λ L_REC` |
| Hard Drive | NVIDIA H200 SXM |

---
## 8. Evaluation Protocol
Detailed in: [`Eval_Protocol_PALADIN.md`](data/docs/Eval_Protocol_PALADIN.md).* 

All grading used the GPT-5 deterministic setup:
model = gpt-5-chat-latest
temperature = 0.0
seed = 42
max_tokens = 1000
response_format = json

---

### **9. Error Taxonomy (ToolScan Aligned)**

| **Category** | **Description** |
|:-------------|:----------------|
| Tool Hallucination | Tool not found or invalid |
| Argument Hallucination | Incorrect or missing parameters |
| Invalid Tool Invocation | Failed tool call |
| Partial Execution | Incomplete tool output |
| Output Hallucination | Fabricated or nonsensical responses |
| Invalid Intermediate Reasoning | Faulty internal planning |
| Re-entrant Failures | Infinite or repeated retries |

*These are mapped in [`toolscan_taxonomy_map.json`](./data/toolscan_taxonomy_map.json).*  

---

### **10. Results Summary**

| **Model** | **TSR** | **RR** | **CSR↓** | **ES↑** |
|:-----------|:-------:|:------:|:---------:|:--------:|
| ToolBench (base) | 0.62 | 0.34 | 0.25 | 0.71 |
| ToolReflect | 0.68 | 0.52 | 0.20 | 0.79 |
| **PALADIN (ours)** | **0.91** | **0.86** | **0.03** | **0.94** |

---
## 11. Reproducibility Checklist
- Deterministic GPT-5 evaluation (temperature = 0)
- Public recovery dictionary and taxonomy maps
- Open annotation, simulation, and training scripts
- Example inputs and outputs for verification
- Hugging Face dataset for full-scale replication

---
## 12. Citations

@inproceedings{paladin2026,
  title     = {PALADIN: Self-Correcting Language Model Agents to Cure Tool-Failure Cases},
  author    = {Anonymous Authors},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year      = {2026}
}

--- 
## 13. License
This repository is released under the MIT License for research and academic use.

---
## 14. Acknowledgements

PALADIN builds upon the foundations of
ToolBench, ToolScan, and ToolReflect,
unifying them under a framework for runtime robustness and recovery learning.

---
> *PALADIN demonstrates that execution-level resilience is learnable —  
> by turning every failure into a training signal.*
