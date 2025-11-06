# PALADIN: Self-Correcting Language Model Agents to Cure Tool-Failure Cases
[![Paper](https://img.shields.io/badge/Paper-ICLR_2026-blue)](https://openreview.net/) 
[![Dataset](https://img.shields.io/badge/Dataset-HuggingFace-orange)](https://huggingface.co/datasets/SriVatsa123/Gemma_Ready_For_PALADIN)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Reproducibility](https://img.shields.io/badge/Reproducibility-✓-brightgreen)](#reproducibility-checklist)

---

### Official Implementation of *“PALADIN: Self-Correcting Language Model Agents to Cure Tool-Failure Cases”*  
*Under review at the International Conference on Learning Representations (ICLR 2026).*

---

## 1. Overview

**PALADIN** is a framework for teaching tool-augmented language models to **detect, diagnose, and recover** from real-time execution failures.  
It extends ToolBench-style agents by introducing *structured failure supervision*, *taxonomy-guided recovery*, and *deterministic GPT-5 evaluation*.  

> **Key Idea:** PALADIN treats failures as data.  
> By injecting and labeling diverse tool-level errors, it learns not only to perform tasks but to *self-repair*.

---

## 2. Repository Structure

PALADIN/
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
