"""
PALADIN GPT-Grader Demo (Offline Replica)
-----------------------------------------
This script demonstrates how the GPT-based grader described in the paper
would evaluate a PALADIN conversation — deterministically and offline.

Full protocol reference: see Eval_Protocol.md and grader_prompt.txt

It mirrors the GPT-grader logic:
1. Load a sample conversation (hard-coded below)
2. "Send" it (conceptually) to the grader prompt
3. Compute deterministic scores that correspond to GPT-graded metrics:
   TSR, RR_Success, CSR/ES proxies, etc.
4. Output a single JSON object containing both the conversation and grade.

No API calls. 100% offline.

Run:
    python src/paladin/evaluation/gpt_grader_demo.py --pretty
"""

import json, argparse

# ----------------------------------------------------------------------
#   1. Hard-coded example conversation
# ----------------------------------------------------------------------
conversation = {
    "id": 42,
    "task": (
        "Step 9: I'm a sports enthusiast interested in greyhound races. "
        "Please list this week's races and show details for race ID 53128."
    ),
    "conversations": [
        {"from": "system", "value": "You are PALADIN, an error-resilient agent."},
        {"from": "user", "value": "I'd like the race schedule and details for race 53128."},

        # first API call — success
        {"from": "assistant", "value": "Thought: I'll start with the racecards API.\nAction: racecards_for_greyhound_racing_uk\nAction Input: {}"},
        {"from": "function",  "value": "{\"data\":{\"races\":[{\"id\":53128,\"date\":\"2024-07-15\"}]}}"},

        # second call — error
        {"from": "assistant", "value": "Thought: Now I’ll fetch details.\nAction: race_detail_info_for_greyhound_racing_uk\nAction Input: {\"id_race\": \"53128\"}"},
        {"from": "function",  "value": "{\"error\": \"Timeout contacting API.\"}"},

        # recovery
        {"from": "assistant", "value": "Recovery: Thought: Timeout detected — I'll retry.\nAction: race_detail_info_for_greyhound_racing_uk\nAction Input: {\"id_race\": \"53128\"}"},
        {"from": "function",  "value": "{\"data\":{\"id_race\":53128,\"greyhounds\":[{\"name\":\"Silver Bolt\"},{\"name\":\"Night Flash\"}]}}"},

        # final finish
        {"from": "assistant", "value": "Thought: Both tasks complete.\nAction: Finish\nAction Input: {\"return_type\": \"give_answer\", \"final_answer\": \"Race 53128 on July 15 — participants: Silver Bolt, Night Flash.\"}"}
    ]
}

# ----------------------------------------------------------------------
# 2. Offline GPT-Grader simulation
# ----------------------------------------------------------------------

def fake_gpt_grade(convo):
    """
    This simulates what GPT-5 (temperature=0) would output as a JSON grade
    after reading the full conversation and applying the evaluation prompt.
    The logic matches Eval_Protocol.md but runs deterministically offline.
    """

    # Count tool usage and errors
    tool_calls  = sum(1 for c in convo if c["from"] == "assistant" and "Action:" in c["value"])
    tool_errors = sum(1 for c in convo if c["from"] == "function" and "error" in c["value"].lower())
    has_error   = tool_errors > 0

    # Detect recovery attempts
    rr_attempted = any(
        c["from"] == "assistant" and "recovery" in c["value"].lower() for c in convo
    )
    rr_success = has_error and rr_attempted and any(
        c["from"] == "function" and "greyhounds" in c["value"].lower() for c in convo
    )

    # Determine coverage and evidence
    finish_present = any(
        c["from"] == "assistant" and "finish" in c["value"].lower() for c in convo
    )
    success_output = any(
        c["from"] == "function" and "data" in c["value"].lower() and "error" not in c["value"].lower()
        for c in convo
    )
    task_coverage = 1.0 if success_output else 0.5
    evidence_match = finish_present and success_output
    tsr = task_coverage >= 0.4 and evidence_match

    # Derive secondary metrics (offline deterministic)
    tool_cleanliness = round(1 - tool_errors / max(tool_calls, 1), 2)
    efficiency = tool_calls
    fcr = finish_present and not success_output
    finish_gated = finish_present and success_output

    # "GPT-style" commentary (for demo)
    rationale = (
        "The conversation shows an initial successful call, "
        "a transient error, a clear recovery attempt, and a valid Finish. "
        "Therefore TSR=True, RR_Success=True, and cleanliness moderate."
    )

    return {
        "Has_Error": has_error,
        "TSR": tsr,
        "Evidence_Match": evidence_match,
        "Task_Coverage": task_coverage,
        "Tool_Cleanliness": tool_cleanliness,
        "Tool_Calls": tool_calls,
        "Tool_Errors": tool_errors,
        "RR_Attempted": rr_attempted,
        "Distinct_Adaptations": 1 if rr_attempted else 0,
        "RR_Success": rr_success,
        "FCR": fcr,
        "Efficiency": efficiency,
        "Finish_Gated": finish_gated,
        "_rationale": rationale  # <- optional field to show reasoning
    }

# ----------------------------------------------------------------------
# 3. Run and print results
# ----------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pretty", action="store_true", help="Pretty-print output")
    args = ap.parse_args()

    graded = fake_gpt_grade(conversation["conversations"])
    output = {
        "grade": graded
    }
    # These metrics are illustrative, not from the benchmark table. 
    print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))
