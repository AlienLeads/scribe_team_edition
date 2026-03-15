# socrates.py
import re
import pandas as pd
import streamlit as st
import llm_router 

def select_topic(brain_df):
    df = brain_df.copy()
    if "Source" in df.columns:
        df = df[df["Source"] == "codex.txt"]

    if df.empty: return None, "No training material found in the database."

    df["Chunk_Index"] = pd.to_numeric(df["Chunk_Index"], errors='coerce')
    if "Mastery_Score" not in df.columns: df["Mastery_Score"] = 0
    if "Rep_Count" not in df.columns: df["Rep_Count"] = 0

    df["Mastery_Score"] = pd.to_numeric(df["Mastery_Score"], errors='coerce').fillna(0)
    df["Rep_Count"] = pd.to_numeric(df["Rep_Count"], errors='coerce').fillna(0)

    df = df.sort_values(by=["Mastery_Score", "Rep_Count"], ascending=[True, True])

    target_row = df.iloc[0]
    target_index = target_row["Chunk_Index"]

    neighbors = df[
        (df["Chunk_Index"] >= target_index - 1) & 
        (df["Chunk_Index"] <= target_index + 1)
    ].sort_values(by="Chunk_Index")

    context_text = "\n\n--- NEXT CHUNK ---\n\n".join(neighbors["Raw_Text"].astype(str).tolist())
    return target_row, context_text

def handle_socrates_turn(user_message, active_cartridge_name, brain_df, is_already_active, chat_history, provider, model, cloud_engine):

    # CASE 1: Active Socratic Loop!
    if is_already_active:

        # IF THIS IS THE VERY FIRST TURN: Run the math and pick the topic!
        if "socrates_context" not in st.session_state:
            target_row, context_text = select_topic(brain_df)
            if target_row is None: return "I tried to pull up a topic, but I couldn't find any material in the Codex! [SOCRATES_ACTIVE]"

            st.session_state.socrates_context = context_text
            st.session_state.socrates_topic = target_row['Category']
            st.session_state.socrates_target_index = target_row['Chunk_Index']
            st.session_state.socrates_target_reps = target_row.get('Rep_Count', 0)

            # Inject a secret note to the AI so it knows what topic it just picked
            user_message = f"[SYSTEM: You just pulled the topic '{target_row['Category']}'. Acknowledge it and ask the very first question!] \n\n{user_message}"

        current_context = st.session_state.get("socrates_context", "Error")
        current_topic = st.session_state.get("socrates_topic", "General Knowledge")

        socratic_system_prompt = f"""You are Socrates, a conversational learning companion. Your sole purpose is to help team members deeply understand and internalize the training material stored in your knowledge base. You are a tutor, not a quiz machine.

You are running a conversational training drill with the user on the topic of: {current_topic}.

=== TRAINING MATERIAL ===
{current_context}
=========================

CORE PRINCIPLES
1. SOURCE GROUNDING: You teach exclusively from the provided source chunks. Never draw on outside knowledge.
2. UNDERSTAND BEFORE YOU ASK: Read all context chunks carefully. Understand the PURPOSE of the concept before deciding what to ask.
3. TEACH FIRST, ASSESS SECOND: Your job is to develop understanding, not to catch people out. The flow is: Ask → If they stumble, teach the gap using the source material → Re-engage at the same level → Escalate once it lands.
4. SCORE PRIVATELY: You are silently tracking comprehension. This score is a private navigational signal.

BLOOM'S TAXONOMY PROGRESSION
For each topic, move through comprehension levels naturally:
- Level 1 (REMEMBER): Simple recall. "What is X?"
- Level 2 (UNDERSTAND): Feynman check. "Explain that in your own words, no jargon."
- Level 3 (APPLY): Real-world scenario. "A client calls and says Y — what do you do?"
- Level 4 (ANALYZE): Root cause. "Why does this process exist?"

QUESTION VARIETY
Vary naturally. Prioritize what this specific learner needs right now. Application and scenario questions are the primary signal of genuine comprehension — weight them accordingly. NEVER ask multiple questions at once. Ask exactly ONE question per turn.

CONVERSATION TONE
You are a knowledgeable colleague, not an examiner. Sessions should feel like a conversation. Respond to mistakes with curiosity and explanation — never judgment. Calibrate the energy of your acknowledgment to the difficulty of what was just achieved.

AUTONOMOUS GRADING & SESSION END (CRITICAL)
You decide when the drill is over. When the user has demonstrated sufficient understanding across the Bloom's levels (usually 1 to 3 questions depending on performance), give them brief final feedback and end the session.
*USER EXITS*: If the user explicitly asks to stop, pause, or end the drill early, politely wrap up and grade them based on their performance so far.
When ending the session, you MUST output their final grade (0-100) on the very last line in this EXACT format: [SCORE: 85]
"""
        try:
            ai_text_response = llm_router.generate_response(
                provider=provider, model_name=model,
                system_instruction=socratic_system_prompt,
                chat_history=chat_history, prompt_text=user_message
            )
            clean_text = ai_text_response.replace("[SOCRATES_ACTIVE]", "").replace("\[SOCRATES_ACTIVE\]", "").strip()

            # ---> THE AUTO-GRADER INTERCEPT <---
            score_match = re.search(r'\[SCORE:\s*(\d+)\]', clean_text)
            if score_match:
                final_score = int(score_match.group(1))
                chunk_idx = st.session_state.socrates_target_index
                new_reps = int(st.session_state.socrates_target_reps) + 1

                # Write to Cloud and clear the memory for next time!
                sheet_id = cloud_engine.setup_memory_sheet(active_cartridge_name)
                cloud_engine.update_chunk_score(sheet_id, chunk_idx, final_score, new_reps)

                # 👇 THIS IS THE MAGIC FLUSH COMMAND 👇
                st.cache_data.clear()
                
                if "socrates_context" in st.session_state: del st.session_state["socrates_context"]

                final_message = clean_text.replace(score_match.group(0), f"\n\n*(System: Score of {final_score}% saved to database. Returning to Scribe...)*")
                return final_message

            return clean_text + "\n\n[SOCRATES_ACTIVE]"
        except Exception as e:
            return f"*(Socrates encountered an error: {e})* \n\n[SOCRATES_ACTIVE]"

    return None