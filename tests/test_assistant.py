"""
Test the full LLM layer end-to-end against live data and your real LLM
endpoint (Qwen via Bitget hackathon access, or whatever you've configured).

Usage:
    python3 tests/test_assistant.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from core.assistant import ask

TEST_QUESTIONS = [
    "How does rNVDA usually react to CPI releases?",
    "Which sectors are most sensitive to CPI surprises?",
    "Is rTSLA's volatility elevated right now?",
    "When's the next FOMC meeting?",
    "What's driving the latest CPI reading — energy or shelter?",
]

if __name__ == "__main__":
    for q in TEST_QUESTIONS:
        print("=" * 60)
        print(f"Q: {q}")
        print("=" * 60)
        try:
            result = ask(q)
            print(f"Tool calls made: {[t['tool'] for t in result['tool_calls_made']]}")
            print(f"Answer: {result['answer']}")
        except Exception as e:
            print(f"[FAILED] {e}")
        print()
