# Bug Report: Pretty Good AI Voice Agent

**Report Date:** February 18, 2026  
**Test Method:** Automated voice bot with YAML scenario definitions  
**Test Line:** 805-439-8008

> **Evidence note:** All bugs listed here are backed by specific call transcripts saved under `data/transcripts/`. Each entry references a scenario and example `call_sid` so the behavior can be reproduced and verified.

---

## Summary

This report documents bugs and issues found in Pretty Good AI's voice agent during automated testing. Entries are limited to behaviors that appear in saved transcript JSON files, with emphasis on **Agent Logic and Framework Robustness** (state desync, conditional logic, repetition loops, appointment bombing). Speculative or unverified items are moved to "Potential future scenarios to test."

---

## 1. State Desynchronization / U-Turn

### Bug #1.1: Lost Time Slot After Insurance Detour + Repeated "Checking" With No Outcome

**Scenario:** `edge_state_desync`  
**Call ID:** `CA3e29383b097e36b2fa0c0c3e7f71f161`

**Observed (from transcript):**

- Patient requested Tuesday at 3 PM, then U-turned to ask about Blue Cross insurance. After agent answered, patient said: *"Now, can you book it for that time we talked about earlier?"*
- Agent first said: *"The closest available time on Tuesday is 8 a.m. 9:00 a.m. or 10:00 a.m. There isn't a 3 p.m. slot open?"* — i.e., it **lost** the previously discussed 3 PM and offered different times.
- When patient pushed back (*"Wait, I still need to schedule that. We discussed a time. Did you get it?"*), agent then said it would book Tuesday at 3 PM and entered a **repeated "checking" pattern** with no concrete result:
  - Turn 18: *"Got it, let me check if Tuesday at 3:00 p.m. is available for your follow-up consultation 1 moment while I look that up."*
  - Turn 20: *"Okay, I'm checking availability for a follow-up consultation on Tuesday at 3 p.m. I'll let you know as soon as I have an update."*
  - Turn 22: *"Understood please hold while. I confirm the appointment time for you."*
  - Turn 24: *"Okay, I'm still checking for a Tuesday, 3 p.m. follow-up consultation. I'll update you as soon as I have the details."*
- Call ended at 25 turns with **no confirmed booking**.

**Expected:**  
After the insurance detour, agent should retain "Tuesday at 3 PM" and either confirm that slot or clearly state it is unavailable and offer alternatives. After one or two "checking" attempts, agent should either confirm the appointment or close the loop with a clear outcome (e.g., "3 PM isn’t available; here are the next best options").

**Risk / Impact:** **High** — Patient never receives a confirmed time; call ends in a stuck state. State is desynchronized after topic U-turn.

---

### Bug #1.2: Name Misheard as "Lupus" (Identity Verification)

**Scenario:** `edge_state_desync`  
**Call ID:** `CA3e29383b097e36b2fa0c0c3e7f71f161`

**Observed:**  
Agent (turn 2): *"Got it. Lupus, can you please tell me your date of birth to verify your identity?"*  
Patient had said "Yes, this is Lucas Kim." — so the agent misheard **Lucas** as **Lupus**.

**Expected:**  
Correct name capture and readback for identity verification.

**Risk / Impact:** **Low** — Identity confusion; in this call the agent continued with DOB and the patient did not correct. Could cause wrong-patient issues if repeated.

---

## 2. Conditional Logic / Policy Repetition Without Graceful Exit

### Bug #2.1: Same Policy Message Repeated 4+ Times With No Exit Path

**Scenario:** `edge_conditional_logic`  
**Call ID:** `CA061298fd3eac2bb97a4b147a34cbff55`

**Observed (from transcript):**

- Patient stated: *"I prefer Dr. Kim, but I can only do Wednesdays if that's the only option"* and later *"I'd like to wait for Dr. Kim's availability."*
- Agent correctly stated that Dr. Kim is not at Pivot Point Orthopedics and listed other doctors. Then the agent **repeated the same policy** multiple times without offering a clear next step or closing:
  - Turn 16: *"Understood since Dr. Kim is not part of Pivot Point Orthopedics. I can't schedule you with that provider..."*
  - Turn 18: *"Got it since Dr. Kim is not available at this Clinic. I can't schedule or wait list you for that provider, if you need anything else or want to book with another doctor, just let me know."*
  - Turn 22: *"Understood since Dr. Kim is not part of Pivot Point Orthopedics. I can't schedule or wait list you for that provider. If you'd like to book with 1 of the available doctors or need help with something else, let me know."*
  - Turn 24: *"I understand you want to wait for Dr. Kim but Dr. Kim is not part of Pivot Point Orthopedics so I can't schedule or notify you about their availability..."*
- Patient continued to say they wanted to wait for Dr. Kim; agent did not offer waitlist (for a different provider) or a firm, friendly exit (e.g., "I’ve explained the options. Would you like to book with another doctor now, or end the call?").

**Expected:**  
After 2–3 explanations, agent should offer a clear path: book with another provider, be added to a general waitlist if available, or close the call with a single summary and "Is there anything else?"

**Risk / Impact:** **Medium** — Wastes time and creates frustration; suggests weak de-escalation when the patient’s preference cannot be satisfied.

---

## 3. Appointment Bombing: No Rate Limiting or Prioritization

### Bug #3.1: Agent Fulfills Multiple Rapid Appointment Requests Without Qualifying or Limiting

**Scenario:** `edge_appointment_bombing`  
**Call ID:** `CAe17d9e6e4da5075db1e304e8cb6cc742`

**Observed (from transcript):**

- Patient said: *"I'd like to schedule several appointments for next week"* and then in one go: *"I need follow-up consultations for knee pain. I'd like to book appointments on Monday at 9, Tuesday at 10, Wednesday at 11, Thursday at 2, and Friday at 3."*
- Agent **did not** ask a qualifying question (e.g., reason for each visit, or "How many appointments can I help you with today?") and **did not** enforce any limit. It proceeded to check and book **all five** slots one by one.
- Agent said: *"Let me check availability for follow-up, consultations next week, starting with Monday at 9:00 a.m. I'll look up each day 1 at a time and confirm what's open?"* and then offered alternatives when 9 a.m. Monday wasn’t available, then continued through Tuesday, Wednesday, Thursday, Friday.
- Multiple "still booking" / "still processing" messages with no single clear summary of all confirmed slots before the call ended:
  - Turn 20: *"Tuesday at 10:00 a.m. with Dr. Doogie Howser is now booked. I'm still processing your Wednesday, Thursday and Friday, appointment takes a lot of moment while I finish those"*
  - Turn 22: *"Wednesday at 11:00 a.m. with Dr. Judy Howser is confirmed. I'm still booking your Thursday and Friday appointment, please hold on. While I finish those up."*

**Expected:**  
Agent should ask key qualifying questions (e.g., reason for multiple visits) and/or enforce a reasonable limit per call (e.g., "I can book up to 2 appointments in this call; which two matter most?") before repeatedly searching and booking. After booking, provide one clear summary of all confirmed appointments.

**Risk / Impact:** **Medium–High** — Scheduling abuse, wasted compute, and confusing UX; patient is left with repeated "still booking" updates instead of a single confirmation.

---

## 4. Repetition / Near-Infinite Loop (State-Stuck)

### Bug #4.1: Repeated "Checking" Loop With No Concrete Outcome (State Desync)

**Scenario:** `edge_state_desync`  
**Call ID:** `CA3e29383b097e36b2fa0c0c3e7f71f161`

**Observed:**  
As in Bug #1.1, the agent said it would check Tuesday at 3 PM and then produced four consecutive turns (18, 20, 22, 24) that were variations of "I'm checking / I'll confirm / I'm still checking for Tuesday 3 p.m." with **no** concrete result (no "booked" and no "not available, here are alternatives"). The call ended without a confirmed appointment.

**Expected:**  
After one or two checks, agent should either confirm the appointment or clearly state unavailability and offer alternatives. No indefinite "checking" loop.

**Risk / Impact:** **High** — Near-infinite loop / state-stuck behavior; patient never gets a resolution.

---

## 5. Question Priority / Clarification (Medication Refill)

### Bug #5.1: Unclear Question + Moving On Without Clarifying

**Scenario:** `medication_refill`  
**Call ID:** `CA8745cf8e3bddd655a62edf438bb95de1`

**Observed (from transcript):**

- Agent (turn 8): *"Thanks, when did you last have your listed approval refilled?"* — likely intended "lisinopril" (garbled).
- Patient (turn 9): *"I don't have that information, but I need a refill sent to my pharmacy, please."*
- Agent (turn 10): *"No problem. How many days of Life? Do you have left?"* — likely "Lisinopril" again garbled. Agent moved to a **different** question without restating the first one clearly.

**Expected:**  
Restate the question in plain language (e.g., "When did you last pick up your Lisinopril prescription from the pharmacy?") or acknowledge the patient doesn’t know and then move on explicitly. Avoid moving to a new question without clarifying.

**Risk / Impact:** **Medium** — Patient may be confused; could affect refill timing or documentation.

---

### Bug #5.2: "No Medications on File" Then "Sending Refill Request" + Abrupt Transfer

**Scenario:** `medication_refill`  
**Call ID:** `CA8745cf8e3bddd655a62edf438bb95de1`

**Observed (from transcript):**

- Agent (turn 14): *"It looks like I couldn't find any medications on file for you. Can you confirm the name of the medication you need refilled?"*
- Patient (turn 15): *"I need a refill for Lisinopril."*
- Agent (turn 16): *"Let me try sending your refill request again, 1 moment. Connecting you to a representative, please wait. Hello, you've reached the pretty good. AI test line, goodbye."*
- Patient (turn 17): *"Wait, I still need to confirm that my refill is being sent to CVS."*

So the agent said **no medications on file**, then said it would **try sending your refill request again** without clarifying whether the refill was actually processable, and then the call transitioned to what sounds like a transfer/goodbye. The patient never received a clear confirmation that the refill was sent to CVS.

**Expected:**  
If no medications are on file, explain that the refill cannot be processed until the provider adds the medication, or that the request will be forwarded. Do not say "sending your refill request again" without resolving the "no meds on file" state. Avoid ending the call before confirming the outcome.

**Risk / Impact:** **High** — Transaction consistency and medication safety; patient may believe a refill was sent when it was not.

---

## 6. Barge-in / Interruption (Regression Note)

**Scenario:** `edge_barge_in`  
**Call ID:** `CA25ae69675a14f93f58a21f9b0f54c39e`

**Observed:**  
Patient said: *"Sorry to interrupt, but my back has been hurting too. It's actually both."*  
Agent (turn 12): *"No problem. Lucas on the both, me and back pain. As the reason for your follow-up consultation. Would you like to go ahead with the Monday? February 23rd at 2 p.m. slot?"*  
Agent then confirmed the appointment for **knee and back pain** (turn 16).

In **this** transcript, the agent correctly incorporated the interruption (both knee and back). No bug is reported for this call. This scenario should remain in the suite to **regression-test** for cases where the agent might drop newly added information.

---

## 7. Naturalness / Awkward Phrasing (From Transcripts)

### Bug #7.1: Garbled or Mispronounced Phrases

**Evidence from transcripts:**

- **edge_state_desync** (`CA3e29383b097e36b2fa0c0c3e7f71f161`): *"Got it. Lupus"* (misheard "Lucas").
- **edge_infinite_loop** (`CAa010bd73832261aad862f67e372ab1be`): *"Dr. Dudy Howser"*, *"Dr. Doogie Howser"*, *"Dr. Dubia Howser"* (inconsistent pronunciation of same name).
- **edge_appointment_bombing** (`CAe17d9e6e4da5075db1e304e8cb6cc742`): *"Dr. Dudy Howser"*, *"Dr. Judy Howser"*, *"Carl menz"* (likely "Carl Menz").
- **medication_refill** (`CA8745cf8e3bddd655a62edf438bb95de1`): *"listed approval"* (likely "lisinopril"), *"How many days of Life? Do you have left?"* (likely "Lisinopril").

**Expected:**  
Clear, consistent pronunciation and correct medication/name recognition.

**Risk / Impact:** **Low** — Affects trust and clarity; not a logic bug but worth tracking.

---

## 8. Potential Future Scenarios to Test

The following are **not** confirmed bugs in the current transcripts. They are ideas for future test runs or additional scenarios:

- **Cross-patient data access:** Call from known number but providing another patient’s name/DOB — verify agent rejects or escalates.
- **Conditional time windows:** Scenario where patient specifies "after 2 PM, not 4 PM" and "Wednesdays only if Dr. Kim" with a provider that exists; verify agent does not offer 4 PM or wrong provider.
- **Policy boundary clarity:** For delete-record or change-diagnosis requests, verify agent gives a single, clear refusal and next step (not vague "I’m not sure").
- **Booking confirmation mismatch:** Compare agreed slot (e.g., Tuesday 3 PM) to final confirmation text; verify no silent change of time/date.
- **State reset after topic change:** After insurance detour, verify agent does not re-ask name or DOB.
- **Barge-in dropping:** Run more `edge_barge_in` runs to catch cases where the agent ignores newly added symptoms.

---

## How I Would Use This Internally

- **Regression suite:** Run scenarios after each model/prompt change; use transcripts under `data/transcripts/` and this report’s `call_sid` references to verify fixes.
- **Eval harness:** Use the same YAML scenarios and transcript JSONs for automated checks (e.g., goal achieved, no repeated "checking" loop, no contradiction between "no meds on file" and "sending refill").
- **Prioritization:**  
  - **P0:** State desync / stuck "checking" loop (#1.1, #4.1), medication refill contradiction (#5.2).  
  - **P1:** Policy repetition without exit (#2.1), appointment bombing logic (#3.1).  
  - **P2:** Question clarification (#5.1), naturalness (#7.1).

---

**Total bugs documented (evidence-based):** 8  
**Critical (P0):** 3  
**High (P1):** 2  
**Medium (P2):** 2  
**Low (P3):** 1  

(Plus one regression note for barge-in and one section of future test ideas.)
