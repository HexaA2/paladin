"""
PALADIN - Simulation with Error Matching
----------------------------------------
Demonstrates PALADIN’s error matching logic: when an unseen tool error occurs,
the agent maps it to the most similar known error type, then executes the
corresponding recovery trajectory deterministically.

This is a simplified, fully offline example for ICLR/AAAI artifact reproducibility.
"""

import json
from typing import List, Dict


# === 1 Known Error Categories (ToolScan Core 7) ===
KNOWN_ERRORS = {
    "TimeoutError": ["timeout", "took too long", "response delay"],
    "JSON Schema Violation": ["invalid json", "schema", "parse", "field missing"],
    "Tool Not Found": ["no such tool", "invalid action", "undefined function"],
    "Rate Limit Exceeded": ["rate limit", "too many requests"],
    "Malformed Input": ["bad request", "invalid parameter", "argument type"],
    "Internal Server Error": ["500", "internal error", "unexpected crash"],
    "Network Failure": ["dns", "network down", "connection refused"]
}


# === 2 Error Matching Logic ===
def match_error(unseen_error: str) -> str:
    """
    Deterministically map an unseen error message to the most similar known error type.
    Uses simple token overlap / substring matching for demonstration.
    """
    unseen = unseen_error.lower()
    best_match, best_score = None, 0

    for known, triggers in KNOWN_ERRORS.items():
        score = sum(1 for trig in triggers if trig in unseen)
        if score > best_score:
            best_match, best_score = known, score

    return best_match or "UnknownError"


# === 3 Mock Tool Simulator ===
def mock_tool_simulator(action: str, action_input: dict) -> str:
    """
    Simulates tool responses, sometimes throwing unseen errors for PALADIN to map.
    """
    if action == "racecards_for_greyhound_racing_uk":
        # Introduce an unseen failure (e.g. "response serialization timeout")
        return json.dumps({"error": "response serialization timeout"})
    elif action == "race_detail_info_for_greyhound_racing_uk":
        return json.dumps({
            "id_race": action_input.get("id_race", "53128"),
            "participants": [
                {"name": "Swift Thunder", "wins": 5},
                {"name": "Blaze Runner", "wins": 3}
            ]
        })
    elif action == "Finish":
        return "The conversation has concluded."
    else:
        return json.dumps({"status": "ok"})


# === 4 PALADIN Simulation Loop with Error Matching ===
def run_error_matching_simulation(task: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Simulates a PALADIN run that encounters an unseen error and applies error matching.
    """
    conversation = []
    system_prompt = (
        "You are **Paladin**, an error-resilient agent that can detect, classify, "
        "and recover from tool failures by mapping unseen errors to known categories.\n\n"
        "Always reason in the format:\nThought:\nAction:\nAction Input:\n"
        "If an unseen error occurs, identify its nearest known error and use the corresponding recovery plan."
    )

    conversation.append({"from": "system", "value": system_prompt})
    conversation.append({"from": "user", "value": task})

    # Step 1: initial tool call
    assistant_output = (
        "Thought: The user wants the race schedule. I'll call the racecards API.\n"
        "Action: racecards_for_greyhound_racing_uk\n"
        "Action Input: {}"
    )
    conversation.append({"from": "assistant", "value": assistant_output})

    # Step 2: tool returns unseen error
    tool_response = mock_tool_simulator("racecards_for_greyhound_racing_uk", {})
    conversation.append({"from": "function", "value": tool_response})

    parsed = json.loads(tool_response)
    unseen_error = parsed.get("error", "")
    matched_error = match_error(unseen_error)

    # Step 3: PALADIN performs error matching recovery reasoning
    recovery_output = (
        f"Thought: I encountered an unseen error — '{unseen_error}'. "
        f"It seems very similar to '{matched_error}', so I will reuse that recovery trajectory.\n"
        "Action: retry_with_reduced_payload\n"
        "Action Input: {\"max_retries\": 1, \"timeout\": 15}"
    )
    conversation.append({"from": "assistant", "value": recovery_output})

    # Step 4: tool retry success
    success_output = json.dumps({
        "races": [
            {"id": "53128", "date": "2025-10-23", "location": "London", "time": "15:00"}
        ]
    })
    conversation.append({"from": "function", "value": success_output})

    # Step 5: PALADIN finishes successfully
    finish_output = (
        "Thought: The retry was successful and I have the race data.\n"
        "Action: Finish\n"
        "Action Input: {\"return_type\": \"give_answer\", "
        "\"final_answer\": \"Recovered from unseen error by mapping it to known type and completing the task.\"}"
    )
    conversation.append({"from": "assistant", "value": finish_output})
    conversation.append({"from": "function", "value": "The conversation has concluded."})

    return {
        "id": 1,
        "task": task,
        "conversations": conversation
    }


# === Example Run ===
if __name__ == "__main__":
    task = (
        "Step 10: I want to see the race schedule for this week and details about race ID 53128. "
        "If a tool call fails unexpectedly, recover gracefully."
    )

    record = run_error_matching_simulation(task)
    print(json.dumps(record, indent=2, ensure_ascii=False))
