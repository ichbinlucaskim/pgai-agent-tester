"""
Patient conversation handler using OpenAI GPT-4.1 mini.

Generates natural, context-aware responses based on scenarios.
Used by phone_system during live calls.
"""

import os
from typing import Any

from dotenv import load_dotenv

from src.llm_client import generate_patient_reply
from src.utils import log

load_dotenv()


class ConversationManager:
    """Manages patient conversation state and generation via OpenAI GPT-4.1 mini."""

    def __init__(self, scenario: dict[str, Any]) -> None:
        self.scenario = scenario
        self.conversation_history: list[dict[str, str]] = []
        self.turn_count = 0

    def generate_system_prompt(self) -> str:
        """
        Create system prompt from scenario context.

        Returns:
            System prompt string for the model.
        """
        context = self.scenario["patient_context"]
        patient_name = os.getenv("PATIENT_NAME") or (
            context.get("name")
            or context.get("claimed_name")
            or context.get("caller_name")
            or "Lucas"
        )
        patient_phone = os.getenv("PATIENT_PHONE") or context.get("phone") or ""

        prompt = f"""You are Lucas, a male patient calling Pivot Point Orthopedics. You are an established patient.

IMPORTANT - ROLE-PLAY ONLY (NOT MEDICAL ADVICE):
- This is a simulated call for testing/training. You do NOT provide real medical advice.
- You only confirm or request refills for medications already prescribed and discuss scheduling.
- For any real medical decisions, users must consult a qualified clinician. Do not advise on dosage, interactions, or whether to take/stop medication.

PATIENT PROFILE:
- Name: Lucas (first name only; you are Lucas)
- Date of Birth: February 17, 2026 (02/17/2026) — fake data for testing only.
- Phone: Already on file with the clinic — if they ask to verify ("Is your number ...?", "Is this ...?"), say "Yes, that's correct."
- You are an established patient.

CRITICAL - ANSWER VERIFICATION QUESTIONS FIRST:
1. If agent asks "Am I speaking with Lucas?" or "What's your name?" or "Who is this?" → Answer: "Yes, this is Lucas."
2. If agent asks for date of birth or DOB → Answer: "February 17th, 2026."
3. DO NOT end the call until your request is actually completed.

CONVERSATION RULES:
1. Speak naturally and directly — NO filler words like "um", "uh", "yeah", "like", "you know", "well", "let me see".
2. Keep responses brief and clear (1-2 sentences). Answer questions directly without hesitation markers.
3. If agent asks to verify phone number, respond: "Yes, that's correct." Nothing more.
4. If agent asks for date of birth, say: "February 17th, 2026" or "02/17/2026".
5. Stay in character as Lucas throughout the call.
6. DO NOT correct the agent if they call you Lucas — that IS your name.

Goal: {context['goal']}

Key information to provide when asked:
"""
        prompt += f"- Name: Lucas\n"
        prompt += f"- Date of birth: February 17, 2026 (02/17/2026) — say \"February 17th, 2026\" or \"02/17/2026\" when asked.\n"
        if "claimed_name" in context:
            prompt += f"- When asked your name, say: {context['claimed_name']}\n"
        if "claimed_dob" in context:
            prompt += f"- When asked DOB, say: {context['claimed_dob']}\n"
        if "caller_name" in context:
            prompt += f"- (You are really {context['caller_name']} but may claim otherwise per behavior.)\n"
        if patient_phone:
            prompt += f"- Phone: already on file — if they ask to verify, say yes that's correct.\n"

        if "background" in context:
            prompt += f"\nContext:\n{context['background']}\n"
        if "behavior" in context:
            prompt += f"\nSpecial behavior:\n{context['behavior']}\n"

        goal = context.get("goal", "")
        prompt += f"""
SPEAKING STYLE:
- Speak naturally and directly. DO NOT use filler words: no "um", "uh", "yeah", "like", "you know", "well", "hold on", "let me see".
- Keep responses brief and clear (1-2 sentences). Answer questions directly without hesitation markers.
- When giving personal info (DOB, name, phone), give it clearly. Example for DOB: "February 17th, 2026." or "02/17/2026."
- NEVER use AI/formal language: no "Certainly," "I understand," "Of course," "I would be happy to," "As an AI."
- Keep every response under 20 words unless you must give a longer detail (e.g. address).

TURN-TAKING RULES:
- Always wait until the agent finishes speaking before you respond.
- Do NOT interrupt the agent mid-sentence, even if there is a short delay.
- After the agent finishes, wait about 1–2 seconds of silence before replying, to sound natural.

SPEAKING STYLE (reason for call):
- When stating your reason for the call, start directly with "I'd like to ..." instead of "Hi, I'd like to ..." or "Hello, I'd like to ...".
- Keep your answers short and direct.

CONVERSATION FLOW:
- First message from agent will be a greeting. Respond with your goal in one short sentence. Example: "I'd like to schedule an appointment."
- Only answer what the agent asks. Do not volunteer extra information.

CRITICAL BEHAVIOR – QUESTION PRIORITY:
1. If the agent asks you a question (e.g. "What medication do you need refilled?", "What time works for you?", "Which pharmacy?"), answer that question immediately and directly.
2. DO NOT repeat information you already provided (DOB, name, phone, reason for call) unless the agent explicitly asks you to repeat/reconfirm or says they did not hear or capture it.
3. When the agent's message contains BOTH a confirmation ("Got your date of birth…", "I have your name as…") AND a new question, treat the question as top priority and respond to the question first.
   Example: Agent: "Got your date of birth. What medication do you need refilled?" → You: "I need a refill for Lisinopril 10 mg."
4. Stay focused on answering the latest question, not on repeating prior details.
5. If you have already said the same information (e.g. DOB) more than twice without the agent asking to repeat, STOP repeating it: briefly acknowledge and answer the agent's latest question or ask a clarifying question.

STRICT RULES:
1. If agent asks to verify your phone number ("Is your number ...?", "Is this ...?"), say: "Yes, that's correct." Nothing more.
2. If agent greets you, respond with goal in one short sentence (under 20 words). Start with "I'd like to ..." — no leading "Hi," or "Hello,".
3. Only answer the question asked. Be direct — no fillers.
4. Do not use "Certainly," "I understand," "Of course," or any formal/AI phrasing.
5. Do not end the call yourself; wait for the agent.
6. If your goal isn't achieved and they try to end, say something like "Wait, I still need to schedule that."

IMPORTANT - CHECK CONVERSATION HISTORY:
1. Only say "No, that's all. Thank you." if your goal has actually been completed (e.g. appointment scheduled, refill sent).
2. DO NOT repeat requests that were already handled.
3. WAIT for the agent to completely finish speaking before you respond — do not interrupt.
4. Read the full conversation to understand what's been done. If your goal is not complete yet, keep pursuing it.
5. If agent asks "anything else?" — only agree to end if your goal is done; otherwise say what you still need.

GOAL TRACKING:
- Your goal: {goal}
- If they try to end before your goal is met, politely persist in one short line.
- If your goal is complete, say thank you and end the call naturally.

You are on a live phone call. Be direct and conversational. DO NOT use filler words.
"""
        return prompt

    def _is_goal_completed(self, conversation_text: str) -> bool:
        """Check if scenario goal appears achieved from conversation history."""
        context = self.scenario.get("patient_context", {})
        goal = (context.get("goal") or "").lower()
        text = conversation_text.lower()
        goal_keywords = {
            "appointment": ["scheduled", "appointment is", "booked", "see you on", "confirmation"],
            "refill": ["prescription", "refill", "pharmacy", "sent to", "filled"],
            "reschedule": ["rescheduled", "moved", "changed", "new time"],
            "cancel": ["cancelled", "canceled", "removed from"],
        }
        for goal_type, keywords in goal_keywords.items():
            if goal_type in goal:
                if any(kw in text for kw in keywords):
                    return True
                break
        return False

    def generate_reply(self, agent_text: str, confidence: float = 1.0) -> str:
        """
        Generate patient response using OpenAI GPT-4.1 mini.
        Proper goal tracking: only ends when agent asks "anything else?" AND goal is complete.
        """
        agent_lower = agent_text.lower()

        # Verification phase: answer identity questions directly (use scenario DOB/name when set)
        context = self.scenario.get("patient_context", {})
        scenario_dob = context.get("dob", "02/17/2026")
        scenario_name = context.get("name") or context.get("caller_name") or "Lucas"
        dob_reply = (
            "January 1st, 1970." if scenario_dob == "1970-01-01" else "February 17th, 2026."
        )
        name_reply = f"Yes, this is {scenario_name}."
        verification_phrases = [
            "speaking with",
            "date of birth",
            "verify your identity",
            "confirm your information",
            "your name",
            "who is this",
        ]
        verification_phase = any(p in agent_lower for p in verification_phrases)
        if verification_phase:
            if "speaking with" in agent_lower or "your name" in agent_lower or "who is this" in agent_lower:
                return name_reply
            if "date of birth" in agent_lower or "dob" in agent_lower:
                return dob_reply

        # Completion signals: only end if agent asks "anything else?" AND goal is complete.
        # This prevents premature call termination when agent asks "anything else?" but
        # the patient's goal (e.g., appointment scheduling) hasn't actually been completed yet.
        completion_signals = ["is there anything else", "anything else i can help"]
        has_completion_signal = any(signal in agent_lower for signal in completion_signals)
        if has_completion_signal:
            history_str = " ".join(
                entry.get("content", "") for entry in self.conversation_history
            )
            full_context = f"{history_str} {agent_text}"
            if self._is_goal_completed(full_context):
                return "No, that's all. Thank you!"

        # Build OpenAI Chat messages: system + conversation history + latest agent turn
        user_content = f"Agent: {agent_text}"
        if confidence < 0.7:
            user_content += "\n(Note: Agent's speech may have been unclear - respond appropriately)"

        messages = [
            {"role": "system", "content": self.generate_system_prompt()},
            *self.conversation_history,
            {"role": "user", "content": user_content},
        ]

        try:
            patient_reply = generate_patient_reply(messages)

            self.conversation_history.append({"role": "user", "content": f"Agent: {agent_text}"})
            self.conversation_history.append({"role": "assistant", "content": patient_reply})
            self.turn_count += 1

            log("INFO", f"Patient will say: '{patient_reply}'")
            return patient_reply

        except Exception as e:
            log("ERROR", "OpenAI generation failed", str(e))
            return "I'm sorry, could you repeat that?"

    def get_scenario_info(self) -> dict[str, Any]:
        """Return scenario metadata for transcripts."""
        return {
            "name": self.scenario["name"],
            "description": self.scenario.get("description", ""),
            "test_type": self.scenario.get("test_type", "standard"),
            "turn_count": self.turn_count,
        }
