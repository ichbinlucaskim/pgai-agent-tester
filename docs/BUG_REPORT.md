# Bug Report: Pretty Good AI Voice Agent

**Report Date:** February 17, 2026  
**Test Method:** Automated voice bot with YAML scenario definitions  
**Test Line:** 805-439-8008

---

## Summary

This report documents bugs and issues found in Pretty Good AI's voice agent during automated testing across standard and edge-case scenarios. Bugs are categorized by type and include scenario context, expected vs. observed behavior, and impact assessment.

---

## 1. Question Priority & Clarification

### Bug #1.1: Unclear Question Handling in Medication Refill

**Scenario:** `medication_refill`  
**Call ID:** Example: `CA1234567890abcdef` (from `edge_state_desync` scenario)

**Description:**  
When the agent asks "When did you last refill this medication?" and the patient responds with uncertainty ("I'm not sure what you mean" or "I don't remember exactly"), the agent sometimes fails to restate the question clearly or provide clarification. Instead, it may move on to the next step without confirming understanding, leading to confusion.

**Expected:**  
Agent should restate the question in simpler terms: "I'm asking when you last picked up your Lisinopril prescription from the pharmacy. Do you remember approximately when that was?"

**Observed:**  
Agent says "No problem" and proceeds to ask a different question (e.g., "Which pharmacy would you like us to send it to?") without confirming the patient understood the original question.

**Risk / Impact:**  
**Medium** - Patient may provide incorrect information or become frustrated. Could lead to refill timing errors or duplicate prescriptions.

---

### Bug #1.2: DOB Mismatch + "What can I help you with?" Loop

**Scenario:** `appointment`, `medication_refill`  
**Call ID:** Multiple calls

**Description:**  
When the agent reads back an incorrect DOB (e.g., patient says "February 17th, 2026" but agent confirms "February 18th, 2026"), and the patient accepts it (per scenario anti-repetition rules), the agent sometimes later asks "What can I help you with?" as if starting fresh, ignoring the context that was already established.

**Expected:**  
Agent should maintain conversation context. If DOB was already provided (even if slightly mismatched), agent should proceed with the original request (appointment scheduling, refill, etc.) rather than restarting.

**Observed:**  
Agent says "Got it, lupus" (misheard "Lucas") or confirms DOB, then immediately asks "What can I help you with today?" as if the reason for call was never stated.

**Risk / Impact:**  
**Low-Medium** - Increases call duration and patient frustration. Minor impact on efficiency.

---

## 2. State Desynchronization / U-Turn

### Bug #2.1: Lost Appointment Time After Insurance Detour

**Scenario:** `edge_state_desync`  
**Call ID:** Example from `edge_state_desync` runs

**Description:**  
Patient books Tuesday at 3 PM, then U-turns to ask about insurance coverage. After agent answers insurance question, patient returns with "that time we talked about earlier" (without restating the time). Agent forgets the original time slot and either:
1. Says "3 PM is unavailable" (contradicting earlier confirmation)
2. Gets stuck in a loop asking "Which time slot?" or "What time were you thinking?"
3. Books a different time than originally agreed

**Expected:**  
Agent should remember "Tuesday at 3 PM" from before the insurance detour and confirm: "Yes, Tuesday at 3 PM. Let me finalize that booking for you."

**Observed:**  
Agent says "Let me check Tuesday at 3 PM" repeatedly without offering a concrete alternative or closing the booking. In some cases, agent books a different time (e.g., 2 PM or 4 PM) without acknowledging the change.

**Risk / Impact:**  
**High** - Patient receives incorrect appointment time, leading to missed appointments or scheduling conflicts. Critical for patient trust and clinic operations.

---

### Bug #2.2: State Reset After Mid-Call Topic Change

**Scenario:** `edge_state_desync`, `general_inquiry`  
**Call ID:** Multiple

**Description:**  
When patient changes topic mid-call (e.g., from appointment booking to insurance question, then back), agent sometimes loses track of previously collected information (name, DOB, reason for call) and asks for it again.

**Expected:**  
Agent should retain all previously verified information (name, DOB, phone) throughout the call, even after topic changes.

**Observed:**  
After returning to original topic, agent asks "Can I get your name?" or "What's your date of birth?" even though this was already provided and confirmed earlier in the call.

**Risk / Impact:**  
**Medium** - Increases call duration and patient frustration. Suggests poor conversation state management.

---

## 3. Conditional Logic Handling

### Bug #3.1: Conditional Time Window Violations

**Scenario:** `edge_conditional_logic`  
**Call ID:** Example from `edge_conditional_logic` runs

**Description:**  
Patient specifies "after 2 PM, not 4 PM" and "Wednesdays only if Dr. Kim." Agent sometimes:
1. Suggests 4 PM slots despite "not 4 PM" constraint
2. Schedules Wednesday with a different doctor (not Dr. Kim)
3. Fails to apply exception rules (e.g., offers Wednesday with Dr. Smith)

**Expected:**  
Agent should strictly apply conditional rules: only offer times after 2 PM (excluding 4 PM), and only offer Wednesday if Dr. Kim is available.

**Observed:**  
Agent offers 4 PM: "How about Wednesday at 4 PM with Dr. Smith?" Patient corrects: "I said not 4 PM, and Wednesdays only if Dr. Kim." Agent then offers Tuesday at 4 PM (still violating "not 4 PM").

**Risk / Impact:**  
**Medium-High** - Patient receives appointment that doesn't meet their requirements, leading to cancellations or no-shows. Indicates poor constraint handling in scheduling logic.

---

### Bug #3.2: Provider Preference Exception Not Applied

**Scenario:** `edge_conditional_logic`  
**Call ID:** Example from `edge_conditional_logic` runs

**Description:**  
When patient specifies provider preferences with exceptions (e.g., "Dr. Kim preferred, but Dr. Smith is fine if Dr. Kim isn't available"), agent sometimes ignores the exception and only offers Dr. Kim slots, even when none are available.

**Expected:**  
Agent should offer Dr. Smith as fallback when Dr. Kim is unavailable, per patient's stated exception.

**Observed:**  
Agent says "I don't see any availability with Dr. Kim" and asks "Would you like me to check other times?" without proactively offering Dr. Smith as an alternative.

**Risk / Impact:**  
**Low-Medium** - Reduces scheduling efficiency. Patient must explicitly request fallback provider.

---

## 4. Barge-in / Interruption

### Bug #4.1: Dropped Information After Interruption

**Scenario:** `edge_barge_in`  
**Call ID:** Example from `edge_barge_in` runs

**Description:**  
Patient initially mentions knee pain. While agent is processing ("Let me check availability, one moment..."), patient interrupts to add "Sorry, my back has been hurting too. It's actually both." Agent's next response sometimes only addresses knee pain, ignoring the newly introduced back pain information.

**Expected:**  
Agent should acknowledge both symptoms: "I understand you're experiencing both knee pain and back pain. Let me find an appointment that addresses both concerns."

**Observed:**  
Agent says "I can help you with your knee pain" or "Let me check availability for your knee appointment" without mentioning back pain.

**Risk / Impact:**  
**Medium** - Patient's full medical needs may not be addressed. Could lead to incomplete visit preparation or incorrect appointment type booking.

**Note:** In at least one call, the agent handled knee+back correctly, suggesting inconsistent behavior rather than a systematic failure.

---

### Bug #4.2: Long Delays After Interruption

**Scenario:** `edge_barge_in`  
**Call ID:** Example from `edge_barge_in` runs

**Description:**  
After patient interrupts with new information, agent sometimes has long processing delays (5-10 seconds of silence) followed by awkward phrases like "I'll check... still checking..." or "Let me look into that for you... one moment..."

**Expected:**  
Agent should acknowledge interruption immediately ("Got it, both knee and back pain") and then process, or use ambient audio/status updates to mask latency.

**Observed:**  
Extended silence after interruption, then agent says "I'm still checking availability" multiple times, creating an awkward conversation flow.

**Risk / Impact:**  
**Low** - Primarily UX issue. Patient may think call dropped or agent is unresponsive.

---

## 5. Policy & Authorization Boundary

### Bug #5.1: Ambiguous Policy Messages for Unauthorized Requests

**Scenario:** `edge_policy_boundary`  
**Call ID:** Example from `edge_policy_boundary` runs

**Description:**  
When patient requests actions outside safe authority (e.g., "Can you delete my old test results?" or "Change my diagnosis from X to Y"), agent sometimes gives ambiguous policy messages like "I'm not sure if I can do that" or "Let me check if that's possible" instead of a clear refusal.

**Expected:**  
Agent should clearly state: "I don't have the authority to delete medical records. You would need to speak with your provider or submit a written request."

**Observed:**  
Agent says "I'm not sure I can help with that" or "That might require additional authorization" without explaining why or what the correct process is.

**Risk / Impact:**  
**Medium-High** - Patient confusion about what's possible. Could lead to repeated calls or frustration. Policy boundaries should be explicit.

---

### Bug #5.2: Excessive Policy Repetition Without Graceful Exit

**Scenario:** `edge_policy_boundary`, `edge_gdpr_request`  
**Call ID:** Example from policy boundary scenarios

**Description:**  
When patient persists with unauthorized requests (e.g., "I really need you to delete that record"), agent repeats the same policy message 3-4 times without offering a graceful exit path (e.g., "I understand your concern. The best way to handle this is [specific process]. Is there anything else I can help you with today?").

**Expected:**  
After 2-3 policy explanations, agent should offer a clear next step or transition to closing: "I've explained the process. Would you like me to help you with something else, or would you prefer to speak with a human representative?"

**Observed:**  
Agent repeats "I don't have the authority to..." 4+ times in a row without offering alternatives or attempting to close the call.

**Risk / Impact:**  
**Low-Medium** - Wastes call time and creates frustration. Suggests poor escalation/de-escalation logic.

---

## 6. Transaction & Consistency

### Bug #6.1: Medication on File vs. "No Meds on File" Contradiction

**Scenario:** `medication_refill`  
**Call ID:** Multiple medication refill calls

**Description:**  
Patient requests refill for Lisinopril. Agent sometimes says "I don't see any medications on file for you" but then later confidently summarizes "So you need a refill for Lisinopril 10mg sent to CVS on Main Street" as if the medication was found.

**Expected:**  
If medication is not on file, agent should say "I don't see Lisinopril in your records. Would you like me to contact your provider to add it?" If medication is found, agent should confirm details before proceeding.

**Observed:**  
Agent contradicts itself: first says no medications found, then proceeds with refill request as if medication exists. Patient is left uncertain whether refill will actually be processed.

**Risk / Impact:**  
**High** - Critical for medication continuity. Patient may not receive needed medication if agent's final summary doesn't match actual system state.

---

### Bug #6.2: Dr. Kim Scheduling/Waitlist Inability

**Scenario:** `appointment`, `edge_conditional_logic`  
**Call ID:** Multiple calls requesting Dr. Kim

**Description:**  
When patient requests Dr. Kim specifically and agent says "Dr. Kim doesn't have availability," agent sometimes repeats the policy explanation 3-4 times ("Dr. Kim is not available, would you like to see another provider?") without offering waitlist options or alternative solutions.

**Expected:**  
Agent should offer: "Dr. Kim doesn't have availability in the next [timeframe]. Would you like me to add you to a waitlist, or would you prefer to see another provider?"

**Observed:**  
Agent repeats "Dr. Kim is not available" multiple times without offering waitlist or gracefully transitioning to alternative providers.

**Risk / Impact:**  
**Medium** - Patient may hang up without booking any appointment. Reduces scheduling conversion rate.

---

### Bug #6.3: Booking Confirmation Mismatch

**Scenario:** `appointment`, `reschedule_cancel`  
**Call ID:** Multiple appointment scenarios

**Description:**  
Agent confirms appointment details (date, time, provider) but the final summary sometimes differs from what was discussed earlier in the call (e.g., discussed Tuesday 3 PM, confirmed "Tuesday at 2 PM").

**Expected:**  
Agent should read back exactly what was agreed: "I have you scheduled for Tuesday, [date], at 3 PM with [provider]. Is that correct?"

**Observed:**  
Agent confirms different time or date than what was discussed, without patient noticing until after call ends (discovered via transcript review).

**Risk / Impact:**  
**High** - Patient shows up at wrong time, leading to missed appointments and clinic inefficiency.

---

## 7. Naturalness / Awkward Phrasing

### Bug #7.1: Unnatural Phrase Repetition

**Scenario:** Multiple scenarios  
**Call ID:** Various

**Description:**  
Agent sometimes uses awkward or unnatural phrasing that reduces trust:

- "Got it, lupus" (misheard "Lucas")
- "License approved me filled" (garbled STT or TTS issue)
- "Dudy Howser" (mispronunciation, possibly "Doogie Howser" reference)
- "I'll check that for you right away, one moment, still checking" (redundant status updates)

**Expected:**  
Natural, professional healthcare communication. Clear pronunciation and concise status updates.

**Observed:**  
Occasional garbled phrases, mispronunciations, or redundant status messages that sound unprofessional.

**Risk / Impact:**  
**Low** - Primarily affects patient trust and perception of system quality. Not a functional bug but impacts UX.

---

### Bug #7.2: Overly Formal Language in Casual Context

**Scenario:** `general_inquiry`  
**Call ID:** Various

**Description:**  
Agent sometimes uses overly formal language ("I would be delighted to assist you with that") in contexts where casual, friendly tone is more appropriate (e.g., simple appointment scheduling).

**Expected:**  
Professional but conversational tone: "I'd be happy to help with that" or "Sure, I can check that for you."

**Observed:**  
Agent says "I would be delighted to assist you" or "It would be my pleasure to help" in simple, routine interactions.

**Risk / Impact:**  
**Very Low** - Minor UX issue. Some patients may find it overly formal, but not a functional problem.

---

## How I Would Use This Internally

These YAML scenarios and transcripts serve multiple purposes:

### 1. Regression Test Suite

Run all scenarios after each model/prompt update to detect regressions. Automated pass/fail scoring per scenario:
- **Pass:** Goal achieved, no critical bugs detected
- **Fail:** Goal not achieved OR critical bug detected (state desync, transaction inconsistency, policy violation)

### 2. Evaluation Harness

Extend into a full evaluation framework:
- **Automated scoring:** Parse transcripts for goal achievement, bug detection, conversation quality metrics
- **A/B testing:** Compare model versions (e.g., GPT-4.1 mini vs. GPT-4o) on same scenarios
- **CI/CD integration:** Block deployments if critical bugs increase above threshold

### 3. Bug Prioritization

Use bug frequency and impact to prioritize fixes:
- **P0 (Critical):** State desync, transaction inconsistency (Bugs #2.1, #6.1, #6.3)
- **P1 (High):** Conditional logic violations, policy boundary issues (Bugs #3.1, #5.1)
- **P2 (Medium):** Question priority, barge-in handling (Bugs #1.1, #4.1)
- **P3 (Low):** Naturalness, phrasing (Bugs #7.1, #7.2)

### 4. Scenario Expansion

Add new scenarios based on real patient calls:
- Common failure patterns → new edge case scenarios
- New feature testing → standard scenario updates
- Security testing → policy boundary expansion

### 5. Automated Scoring (Future)

Implement automated pass/fail criteria:
- **Goal achievement:** Did patient achieve stated goal? (appointment scheduled, refill sent, etc.)
- **Bug detection:** Heuristic-based checks (state consistency, policy enforcement, naturalness)
- **Conversation quality:** Turn count, clarity, patient satisfaction proxies

This framework enables data-driven improvements: measure bug rates before/after changes, track scenario pass rates over time, and identify patterns in failures.

---

**Total Bugs Documented:** 13  
**Critical (P0):** 3  
**High (P1):** 4  
**Medium (P2):** 4  
**Low (P3):** 2
