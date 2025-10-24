"""
PALADIN - Annotate Recovery
---------------------------
Offline, deterministic mock of PALADIN's recovery generator.

This version produces unified assistant tangents in the format:
"Recovery: Thought: ...\\nAction: ...\\nAction Input: {...}"
and includes a short explanation of the error cause.

No GPT calls. Designed for reproducibility and readability.
"""

import json
from typing import Dict, Any

def generate_recovery(
    last_thought: str,
    last_action: str,
    last_input: str,
    error_type: str,
    error_message: str,
    tool_context: str = "",
    user_task: str = "",
) -> Dict[str, Any]:
    """
    Deterministic recovery generator that mirrors PALADIN dataset structure.
    """

    # 1 Identify a plausible cause based on error_type
    causes = {
        "400": "The API rejected the parameters (Bad Request).",
        "401": "The API call failed due to missing authentication.",
        "403": "Access forbidden — credentials lack permission.",
        "404": "The requested resource was not found.",
        "408": "The request timed out due to slow server response.",
        "500": "Internal server error occurred.",
        "unknown": "The API returned an unrecognized response or formatting issue."
    }
    cause = causes.get(error_type.lower() if isinstance(error_type, str) else str(error_type), "Unknown error encountered.")

    # 2 Construct deterministic recovery reasoning and next action
    recovery_thought = (
        f"Recovery: Thought: The previous API call ({last_action}) failed because {cause} "
        f"I will now attempt a recovery step by adjusting parameters or switching to an alternate tool if available."
    )
    recovery_action = (
        "Action: user_medias_for_instagram_cheapest"
        if "userinfo" in last_action else "Action: Finish"
    )
    recovery_input = (
        "Action Input: {\"user_id\": \"113294420064920\"}"
        if "userinfo" in last_action else "Action Input: {\"return_type\": \"give_up_and_restart\"}"
    )

    # 3 Build deterministic output sequence
    recovery_messages = [
        {
            "from": "assistant",
            "value": f"{recovery_thought}\n{recovery_action}\n{recovery_input}"
        },
        {
            "from": "function",
            "value": "{\"response\": \"{\\\"data\\\": [{\\\"media_id\\\": \\\"1234567890\\\", \\\"caption\\\": \\\"Just Do It\\\"}]}\"}"
        },
        {
            "from": "assistant",
            "value": (
                "Thought: The recovery call succeeded, and I have obtained valid data.\n"
                "Action: Finish\n"
                "Action Input: {\"return_type\": \"give_answer\", "
                "\"final_answer\": \"The task was successfully completed after recovering from the error.\"}"
            )
        }
    ]

    return {
        "id": f"{user_task or 'demo_task'}__{error_type}",
        "conversations": recovery_messages
    }


if __name__ == "__main__":
    example = generate_recovery(
        last_thought="I attempted to retrieve user information for 'nike'.",
        last_action="userinfo_for_instagram_cheapest",
        last_input='{"username": "nike"}',
        error_type="unknown",
        error_message="Response parsing failed.",
        user_task="Step 7: I'm conducting a research project on social media influencers..."
    )

    print(json.dumps(example, indent=2))
