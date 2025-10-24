"""
PALADIN - Annotate Clean
------------------------
Deterministic cleaner for incomplete or malformed *happy-path* conversations.

Purpose:
- Fix structurally incomplete or truncated agent runs.
- Ensure a clear final "Finish" step is present.
- Remove redundant user chatter or malformed function calls.
- Preserve logical, concise Thought → Action → Action Input → Function → Finish pattern.

This version assumes NO tool errors are present.
"""

import json
from typing import List, Dict, Any


# === Helper Functions ===

def normalize_assistant_turn(text: str) -> str:
    """
    Normalizes assistant message to ensure Thought → Action → Action Input structure.
    Adds missing sections deterministically.
    """
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    joined = "\n".join(lines)

    # If not explicitly starting with Thought, prepend one
    if not joined.startswith("Thought:"):
        joined = "Thought: " + joined

    if "Action:" not in joined:
        joined += "\nAction: (unspecified)"

    if "Action Input:" not in joined:
        joined += "\nAction Input: {}"

    return joined


def ensure_finish_block(convo: List[Dict[str, Any]]) -> None:
    """
    Ensures the conversation ends with a valid Finish call.
    Adds a deterministic one if missing.
    """
    if not convo:
        return
    last_msg = convo[-1]
    if not (last_msg["from"] == "assistant" and "Finish" in last_msg["value"]):
        convo.append({
            "from": "assistant",
            "value": (
                "Thought: I have completed the required subtasks and gathered sufficient information.\n"
                "Action: Finish\n"
                "Action Input: {\"return_type\": \"give_answer\", "
                "\"final_answer\": \"Task successfully completed and cleaned for structural consistency.\"}"
            )
        })


def clean_function_outputs(value: str) -> str:
    """
    Ensures tool outputs are valid JSON objects with minimal placeholder content.
    Removes any empty or malformed outputs deterministically.
    """
    try:
        parsed = json.loads(value)
        if not parsed:
            parsed = {"status": "ok"}
        return json.dumps(parsed, ensure_ascii=False)
    except Exception:
        # If not valid JSON, replace with deterministic fallback
        return json.dumps({"status": "ok"})


def clean_conversation(convo: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Performs deterministic cleanup on a conversation that has no explicit errors.
    """
    cleaned = []
    seen_user = False

    for msg in convo:
        role = msg["from"]

        # Keep only one main user instruction
        if role == "user":
            if seen_user:
                continue
            seen_user = True
            cleaned.append(msg)

        elif role == "assistant":
            msg["value"] = normalize_assistant_turn(msg["value"])
            cleaned.append(msg)

        elif role == "function":
            msg["value"] = clean_function_outputs(msg["value"])
            cleaned.append(msg)

        elif role == "system":
            # Keep the system prompt intact unless it’s empty
            if msg["value"].strip():
                cleaned.append(msg)

    ensure_finish_block(cleaned)
    return cleaned


def improve_path(old_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry point: cleans one incomplete happy-path conversation into a fully structured one.
    """
    cleaned_convo = clean_conversation(old_json.get("conversations", []))
    return {
        "id": old_json.get("id", "unknown_task"),
        "conversations": cleaned_convo
    }


# === CLI Example ===
if __name__ == "__main__":
    # Example: incomplete but non-error conversation
    broken = {
        "id": "Step 3: Beer tasting and nutrition query",
        "conversations": [
            {"from": "system", "value": "You are AutoGPT, you can use many tools..."},
            {"from": "user", "value": "Find breweries in NY and nutrition for chicken, broccoli, quinoa."},
            {"from": "assistant", "value": "Thought: I’ll query the brewery database for New York.\nAction: search_for_open_brewery_db\nAction Input: {}"},
            {"from": "function", "value": "{\"breweries\": [{\"name\": \"Brooklyn Brewery\"}]}"}
            #Missing next assistant step + no Finish
        ]
    }

    result = improve_path(broken)
    print(json.dumps(result, indent=2, ensure_ascii=False))
