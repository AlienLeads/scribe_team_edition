import re
import json
import argparse
import llm_router
from datetime import datetime
from drive_api import CloudEngine

def elastic_bucket_chunker(raw_text, target_words=400):
    # NEW UNIVERSAL SPLITTER: Splits by newlines OR end-of-sentence punctuation!
    blocks = re.split(r'\n+|(?<=[.!?])\s+', raw_text)
    chunks = []
    current_chunk = []
    current_word_count = 0

    for block in blocks:
        block = block.strip()
        if not block: continue
        words_in_block = len(block.split())

        if current_word_count + words_in_block >= target_words and current_word_count > 0:
            # Join with a space instead of a double-newline so sentences flow naturally
            chunks.append(" ".join(current_chunk))
            current_chunk = [block]
            current_word_count = words_in_block
        else:
            current_chunk.append(block)
            current_word_count += words_in_block

    if current_chunk: chunks.append(" ".join(current_chunk))
    return chunks

def main():
    # 1. Listen for the specific Mission Name from the terminal (or Scribe UI later)
    parser = argparse.ArgumentParser()
    parser.add_argument("--mission", required=True, help="The exact name of the Cartridge to process")
    args = parser.parse_args()
    target_mission = args.mission

    print(f"🚀 Waking up Scribe Worker for: '{target_mission}'")
    cloud = CloudEngine()

    # 2. Find or Create the Spreadsheet Brain
    sheet_id = cloud.setup_memory_sheet(target_mission)
    if not sheet_id:
        print("❌ Could not locate or create the Spreadsheet. Exiting.")
        return

    print("📖 Reading codex.txt...")
    raw_text = cloud.read_file(target_mission, "codex.txt")

    if raw_text == "[FILE NOT FOUND IN CLOUD]" or not raw_text.strip():
        print("⚠️ No readable text found. Exiting.")
        return

    # ==========================================
    # THE GHOST MARKER: Slice off the old stuff!
    # ==========================================
    last_chunk = cloud.get_last_processed_chunk(sheet_id)
    if last_chunk and last_chunk in raw_text:
        print("👻 Ghost Marker found! Slicing off previously processed logs...")
        raw_text = raw_text.split(last_chunk)[-1]
        if not raw_text.strip():
            print("✅ All logs are already in the Spreadsheet Brain. Nothing new to process!")
            return
    else:
        print("🌱 No Ghost Marker found. Processing entire log from the beginning...")

    # 3. Chunk the NEW text
    print("🪣 Pouring new text into Elastic Buckets...")
    chunks = elastic_bucket_chunker(raw_text, target_words=400)
    print(f"🎯 Yield: {len(chunks)} new chunks to process.")

    # 4. Route to Gemini and Save
    if chunks:
        print("🔢 Calculating starting Chunk Index...")
        existing_rows = cloud.get_all_sheet_rows(sheet_id)
        starting_index = max(0, len(existing_rows) - 1) if existing_rows else 0

        print("🧠 Routing to Gemini for Metadata Tagging...")
        for i, chunk in enumerate(chunks):
            print(f"   Processing chunk {i+1} of {len(chunks)}...")

            system_prompt = """You are a data extraction AI. 
            Analyze the text and return ONLY a valid JSON object with exactly these keys:
            {"Category": "string", "Keywords": "string, string", "Summary": "string"}"""

            try:
                raw_response = llm_router.generate_response(
                    provider="gemini", model_name="gemini-2.5-flash",
                    system_instruction=system_prompt, chat_history=[], prompt_text=chunk
                )

                json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                if json_match:
                    metadata = json.loads(json_match.group(0))
                else:
                    metadata = {"Category": "Error", "Keywords": "Parse_Failed", "Summary": "No JSON found."}
            except Exception as e:
                metadata = {"Category": "Error", "Keywords": "API_Failed", "Summary": str(e)}

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_chunk_index = starting_index + i

            # We ONLY send the 7 core columns. Google Sheets leaves Mastery_Score (H) and Rep_Count (I) blank for Socrates!
            row_data = [
                timestamp, 
                "codex.txt", 
                chunk,
                metadata.get("Category", "Unknown"), 
                metadata.get("Keywords", "Unknown"), 
                metadata.get("Summary", "No summary."),
                current_chunk_index 
            ]

            cloud.append_sheet_row(sheet_id, row_data)
            print(f"   ✅ Saved to Sheet! Category: {metadata.get('Category')} | Index: {current_chunk_index}")

    print("\n🏁 Worker execution complete.")

if __name__ == "__main__":
    main()