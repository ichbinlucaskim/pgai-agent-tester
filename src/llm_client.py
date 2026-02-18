"""
Centralized OpenAI LLM client for patient reply generation.

Uses GPT-4.1 mini for all patient bot responses. Single entry point:
generate_patient_reply(messages) for the /handle-agent-response flow.
"""

import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def generate_patient_reply(messages: list[dict[str, Any]]) -> str:
    """
    Generate patient reply using GPT-4.1 mini.

    messages: OpenAI Chat API format, e.g.:
      [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
        ...
      ]
    """
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.4,
        max_tokens=256,
    )

    choice = response.choices[0]
    text = (choice.message.content or "").strip()

    # Guard: avoid ultra-short or incomplete replies that sound unnatural.
    # Filters out empty responses, very short fragments (< 8 chars), and incomplete
    # phrases that the model sometimes generates when uncertain.
    if not text or len(text) < 8 or text.lower() in {"i need", "i would like"}:
        return "I'm sorry, could you repeat that?"

    return text
