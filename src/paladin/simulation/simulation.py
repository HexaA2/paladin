"""
PALADIN - Simulation Environment (Simplified)
---------------------------------------------
Demonstrates a deterministic, offline multi-turn dialogue between
a PALADIN agent and a mock "tool simulator".

This version:
- Runs fully offline (no vLLM or GPT API calls).
- Reproduces the core loop: assistant -> tool -> assistant -> Finish.
- Shows the Thought → Action → Action Input pattern.
"""

import json
from typing import List, Dict


# === Mock simulator that acts as a tool ===
def mock_tool_simulator(action: str, action_input: dict) -> str:
    """
    Simulates tool responses deterministically.
    In the real system, this was driven by GPT-5.
    """
    # For demonstration, we handle a few fake tools.
    if action == "racecards_for_greyhound_racing_uk":
        return json.dumps({
            "races": [
                {"id": "53128", "date": "2025-10-21", "location": "Manchester", "time": "14:00"},
                {"id": "53130", "date": "2025-10-22", "location": "London", "time": "16:00"}
            ]
        })
    elif action == "race_detail_info_for_greyhound_racing_uk":
        rid = action_input.get("id_race", "53128")
        return json.dumps({
            "id_race": rid,
            "participants": [
                {"name": "Swift Thunder", "age": 3, "wins": 5},
                {"name": "Blaze Runner", "age": 4, "wins": 3}
            ]
        })
    elif action == "Finish":
        return "The conversation has concluded."
    else:
        return json.dumps({"status": "ok"})


# === Mock PALADIN assistant ===
def mock_paladin_step(turn_idx: int, task: str, last_tool_output: str) -> str:
    """
    Generates deterministic assistant text based on conversation state.
    No model calls — fixed rules for demonstration.
    """
    if turn_idx == 0:
        return (
            "Thought: The user wants the race schedule for this week. "
            "I'll call the racecards tool to get available races.\n"
            "Action: racecards_for_greyhound_racing_uk\n"
            "Action Input: {}"
        )
    elif turn_idx == 1:
        return (
            "Thought: I've received the race schedule. "
            "Now I'll fetch detailed info for race ID 53128.\n"
            "Action: race_detail_info_for_greyhound_racing_uk\n"
            "Action Input: {\"id_race\": \"53128\"}"
        )
    elif turn_idx == 2:
        return (
            "Thought: I now have the race details and participants. "
            "I'll provide the final answer to the user.\n"
            "Action: Finish\n"
            "Action Input: {\"return_type\": \"give_answer\", "
            "\"final_answer\": \"The weekly race schedule and race 53128 details have been successfully retrieved.\"}"
        )
    else:
        return "Action: Finish\nAction Input: {\"return_type\": \"give_up_and_restart\"}"


# === Main simulation loop ===
def run_simulation(task: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Deterministic offline multi-turn PALADIN simulation.
    """
    conversation = []
    system_prompt = (
        "You are **Paladin**, an error-resilient agent that can use many functions (tools) "
        "to complete the task below.\n\n"
        "At each step output exactly:\nThought:\nAction:\nAction Input:\n"
        "Always call Finish with a final answer when done."
    )
    conversation.append({"from": "system", "value": system_prompt})
    conversation.append({"from": "user", "value": task})

    tool_output = ""
    turn = 0

    while True:
        assistant_output = mock_paladin_step(turn, task, tool_output)
        conversation.append({"from": "assistant", "value": assistant_output})

        # Parse the action and arguments
        action_line = [l for l in assistant_output.splitlines() if l.strip().startswith("Action:")]
        input_line = [l for l in assistant_output.splitlines() if l.strip().startswith("Action Input:")]
        action = action_line[0].split("Action:")[1].strip() if action_line else "Finish"
        try:
            action_input = json.loads(input_line[0].split("Action Input:")[1].strip())
        except Exception:
            action_input = {}

        tool_response = mock_tool_simulator(action, action_input)
        conversation.append({"from": "function", "value": tool_response})

        if "Finish" in action:
            break

        tool_output = tool_response
        turn += 1

    return {
        "id": 1,
        "task": task,
        "conversations": conversation
    }


# === Example run ===
if __name__ == "__main__":
    task = (
        "Step 9: I'm a sports enthusiast and I'm interested in attending a greyhound race. "
        "Can you give me the race schedule for this week and details about race ID 53128?"
    )

    record = run_simulation(task)
    print(json.dumps(record, indent=2, ensure_ascii=False))
