# Appendix Reference Links

This document provides direct references to the paper sections and appendices where each dataset, table, or artifact in this repository is described in detail.

---

## Appendix C — Runtime Errors
- **Source file:** [`data/recovery_dictionary.json`](../data/recovery_dictionary.json)
- **Description:** Enumerates all simulated runtime and API-level errors (HTTP 400–599, schema violations, tool execution exceptions).
- **Expanded content:** Includes error–recovery pairs referenced in Table 2 of the paper.
- **Paper excerpt:** “For the rest of the errors used to train this model, check out our GitHub.”

---

## Appendix G — Recovery Strategies
- **Source file:** [`data/recovery_dictionary.json`](../data/recovery_dictionary.json)
- **Description:** Details PALADIN’s recovery dictionary, consisting of 55+ exemplar failures and their corresponding recovery strategies.
- **Notes:** Aligns with ToolScan’s 7 error taxonomy categories (see `data/toolscan_taxonomy_map.json`).

---

## Appendix I — Evaluation Framework
- **Source file:** [`data/eval_protocol.md`](../data/eval_protocol_PALADIN.md)
- **Description:** Defines PALADINEval and ToolReflectEval procedures, including metrics:
  - **RR** (Recovery Rate)
  - **TSR** (Task Success Rate)
  - **CSR** (Cascaded Success Rate)
  - **ES** (Efficiency Score)
- **Includes:** Grading rubric for GPT-5-based evaluation and sample traces.

---

## Appendix J — Generalization Experiments
- **Source file:** [`figures/generalization_results/`](../figures/generalization_results/)
- **Description:** Contains JSON summaries of model performance across unseen error domains and tool environments.

---

## Appendix K — Error Taxonomy Alignment
- **Source file:** [`data/toolscan_taxonomy_map.json`](../data/toolscan_taxonomy_map.json)
- **Description:** Maps all recovery dictionary entries into the **ToolScan-7 taxonomy**:
  1. Tool Hallucination → tool not found errors  
  2. Argument Hallucination → missing or invalid tool input  
  3. Invalid Tool Invocation → tool call failed  
  4. Partial Execution → incomplete tool outputs requiring continuation  
  5. Output Hallucination → tool output not valid  
  6. Invalid Intermediate Reasoning → corrected plans and backtracking in multi-turn dialogues  
  7. Re-entrant Failures → handled via explicit retry and fallback logic

---

## Additional Resources
- **Figures:** `figures/Simulation_Figure.png`, `figures/Annotation_Figure.png`
- **Code demos:** `src/paladin` — Code demonstrations highlighting key logic and processes behind PALADIN.

---

_Last updated: October 2025_
