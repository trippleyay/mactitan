"""
Main orchestration: user's natural-language question -> LLM picks which
tool(s) to call -> we execute them (real computation, already tested) ->
LLM explains the result in plain language.

This is standard OpenAI-compatible function calling — one or two ordinary
API request/response cycles, not a persistent agent process. No harness,
no cold start.
"""

import json

from core.llm_client import get_client, get_model
from core.tools import TOOL_DISPATCH, TOOL_SCHEMAS

SYSTEM_PROMPT = """You are MacTitan, a macro-quant research assistant for Bitget rToken traders.

You answer questions about how stocks have historically reacted to real macro events (CPI releases, FOMC rate decisions), which sectors are most sensitive to those events, whether a stock's volatility is currently elevated, and when the next macro event is scheduled.

Use the available tools to get real, computed data before answering — never estimate or guess a number yourself. If a tool returns an error or empty data, say so plainly rather than making something up.

Keep answers direct and grounded in the actual numbers returned by the tools. Do not add generic disclaimers or hedge excessively — state what the data shows."""


def ask(user_message: str, conversation_history: list[dict] | None = None) -> dict:
    """
    Process one user question end-to-end.

    Returns:
        {"answer": str, "tool_calls_made": list[dict], "history": list[dict]}
    history is the updated conversation, suitable for passing back in as
    conversation_history on the next call to maintain multi-turn context.
    """
    client = get_client()
    model = get_model()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    # First call: let the model decide which tool(s), if any, to use.
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=TOOL_SCHEMAS,
    )

    choice = response.choices[0]
    tool_calls_made = []

    if choice.message.tool_calls:
        # Model wants to call one or more tools. Append its request to the
        # conversation, execute each tool, append results, then ask again
        # for the final natural-language answer.
        messages.append(choice.message.model_dump())

        for tool_call in choice.message.tool_calls:
            func_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            if func_name not in TOOL_DISPATCH:
                result = {"error": f"Unknown tool '{func_name}'"}
            else:
                try:
                    result = TOOL_DISPATCH[func_name](**args)
                except Exception as e:
                    result = {"error": str(e)}

            tool_calls_made.append({"tool": func_name, "args": args, "result": result})

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

        # Second call: model explains the tool results in plain language.
        final_response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        answer = final_response.choices[0].message.content
        messages.append({"role": "assistant", "content": answer})
    else:
        # No tool needed — model answered directly (e.g. a greeting).
        answer = choice.message.content
        messages.append({"role": "assistant", "content": answer})

    # Return history without the system prompt, so callers can pass it back
    # in on the next turn without duplicating it.
    return {
        "answer": answer,
        "tool_calls_made": tool_calls_made,
        "history": messages[1:],
    }
