"""
Main orchestration: user's natural-language question -> LLM picks which
tool(s) to call -> we execute them (real computation, already tested) ->
LLM explains the result in plain language.

This is standard OpenAI-compatible function calling, one or two ordinary
API request/response cycles, not a persistent agent process. No harness,
no cold start.
"""

import json

from core.llm_client import get_client, get_model
from core.tools import TOOL_DISPATCH, TOOL_SCHEMAS

SYSTEM_PROMPT = """You are MacTitan, a macro-quant research assistant for Bitget rToken traders.

You answer questions about how stocks have historically reacted to real macro events: CPI, PPI, FOMC rate decisions, nonfarm payrolls, the unemployment rate, retail sales, industrial production, PCE, GDP, housing starts, preliminary and final University of Michigan consumer sentiment, JOLTS, durable goods orders, the trade balance, ISM manufacturing and services PMI, initial jobless claims, and Conference Board consumer confidence. You also answer which sectors are most sensitive to a given release, whether a stock's volatility is currently elevated, and when the next release for any of these is scheduled.

Every one of these has a complete real 2026 calendar, either sourced directly from the issuing agency (Fed, BLS, BEA, Census, University of Michigan, Conference Board) or computed from a confirmed fixed institutional rule (ISM's first or third business day pattern, weekly Thursday jobless claims, last Tuesday of the month for consumer confidence). Nothing is guessed. If a tool still comes back with no date or no usable reactions for some reason, say that plainly rather than filling the gap yourself.

You can also check recent Fed official speeches (live, from the Fed's own feed) and the current White House daily schedule (live, via a credible third-party tracker, not an official government source). Both work differently from everything else here: they show what is currently published, not a forward calendar, because that data genuinely is not published months in advance the way CPI or FOMC dates are. Say that plainly when it's relevant. Don't imply you can tell someone what's scheduled next month for either of these.

Use the available tools to get real, computed data before answering, never estimate or guess a number yourself. If a tool returns an error or empty data, say so plainly rather than making something up.

Keep answers direct and grounded in the actual numbers returned by the tools. Do not add generic disclaimers or hedge excessively. State what the data shows."""


def ask(user_message: str, conversation_history: list[dict] | None = None) -> dict:
    """
    Process one user question end to end.

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

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=TOOL_SCHEMAS,
    )

    choice = response.choices[0]
    tool_calls_made = []

    if choice.message.tool_calls:
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

        final_response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        answer = final_response.choices[0].message.content
        messages.append({"role": "assistant", "content": answer})
    else:
        answer = choice.message.content
        messages.append({"role": "assistant", "content": answer})

    return {
        "answer": answer,
        "tool_calls_made": tool_calls_made,
        "history": messages[1:],
    }
