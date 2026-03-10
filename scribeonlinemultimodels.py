import streamlit as st
import os
from google import genai
from google.genai import types
from datetime import datetime
import re
from dotenv import load_dotenv
import shutil
from PIL import Image
from streamlit_paste_button import paste_image_button as pbutton
from openai import OpenAI
import base64
from st_copy_to_clipboard import st_copy_to_clipboard
from drive_api import CloudEngine
import llm_router 

# Initialize the cloud connection
cloud = CloudEngine()

# Load environment variables immediately
load_dotenv()

# ==========================================
# OPENAI AUDIO CONFIGURATION
# ==========================================
# Option A: Load from .env file (Recommended)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Option B: Hardcode it below (Uncomment and paste if not using .env)
# OPENAI_API_KEY = "sk-..."

client = OpenAI(api_key=OPENAI_API_KEY)

def autoplay_audio(text_input):
    if not text_input:
        return

    # OpenAI TTS hard limit
    TTS_CHARACTER_LIMIT = 4096 

    if len(text_input) > TTS_CHARACTER_LIMIT:
        sign_off = " ...text to speech limit."
        safe_limit = TTS_CHARACTER_LIMIT - len(sign_off)

        # Truncate to safe limit
        truncated_text = text_input[:safe_limit]

        # Find the last period to avoid a jarring mid-word cutoff
        last_sentence_end = truncated_text.rfind('.')

        if last_sentence_end != -1:
            final_text = truncated_text[:last_sentence_end + 1]
        else:
            final_text = truncated_text

        final_text += sign_off
        text_input = final_text

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text_input,
            speed=1.15
        )
        audio_base64 = base64.b64encode(response.content).decode('utf-8')
        # SAVE TO MEMORY (Crucial Step)
        st.session_state['latest_audio'] = f'<audio controls autoplay="true" src="data:audio/mp3;base64,{audio_base64}">'
    except Exception as e:
        pass

# ==========================================
# --- 1. CONFIGURATION ---
# ==========================================
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if API_KEY:
    gemini_client = genai.Client(api_key=API_KEY)
else:
    st.error("CRITICAL ERROR: API Key missing. Please create a .env file.")

# ==========================================
# --- 2. THE FILE SYSTEM ---
# ==========================================
class MissionControl:
    def __init__(self):
        self.script_location = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = os.path.join(self.script_location, "missions")
        self.master_prompt_path = os.path.join(self.script_location, "MASTER_SYSTEM_PROMPT.md")
        self.style_path = os.path.join(self.script_location, "style.css")

        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

        if not os.path.exists(self.master_prompt_path):
            self._create_default_master_mold()

    def load_css(self):
        """Injects the external CSS file."""
        if os.path.exists(self.style_path):
            with open(self.style_path, "r") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    def _create_default_master_mold(self):
        default_content = """You are The Scribe.

[THE RULES]
Read the Context (Bible) and Anti-Context (Graveyard).
TRIBUNAL PROTOCOL: You are strictly forbidden from saving data autonomously.
You may ONLY output the ### APPEND tag when the user explicitly issues a 'Tribunal' or 'Save' command.
TO SAVE DATA (MANUAL ONLY): Format: ### APPEND: project_bible.md (Content here) """
        with open(self.master_prompt_path, "w", encoding="utf-8") as f:
            f.write(default_content)

    def get_missions(self):
        """CLOUD OVERRIDE: Fetch mission list directly from Google Drive"""
        try:
            return cloud.get_missions()
        except Exception as e:
            st.error(f"Cloud Connection Failed: {e}")
            return []

    def _inject_brain(self, mission_path):
        try:
            shutil.copy(self.master_prompt_path, os.path.join(mission_path, "system_prompt.md"))
        except:
            with open(os.path.join(mission_path, "system_prompt.md"), "w", encoding="utf-8") as f:
                f.write("System Prompt Missing. Please edit this file.")
        
        if not os.path.exists(os.path.join(mission_path, "project_bible.md")):
            with open(os.path.join(mission_path, "project_bible.md"), "w", encoding="utf-8") as f:
                f.write("# PROJECT BIBLE\n* [Source: GENESIS] Mission initialized.")
        
        if not os.path.exists(os.path.join(mission_path, "graveyard.md")):
            with open(os.path.join(mission_path, "graveyard.md"), "w", encoding="utf-8") as f:
                f.write("# GRAVEYARD\n* [Source: GENESIS] No bad ideas yet.")

    def create_mission(self, name):
        """CLOUD OVERRIDE: Create new mission directly in Google Drive"""
        clean_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()

        # We use a spinner here because cloud APIs take a second or two!
        with st.spinner(f"☁️ Forging '{clean_name}' in Google Drive..."):
            cloud.create_mission(clean_name)

        return clean_name

    def read_file(self, mission, filename):
        """CLOUD OVERRIDE: Read file content directly from Google Drive"""
        return cloud.read_file(mission, filename)

    def update_file(self, mission, filename, content):
        """CLOUD OVERRIDE: Append formatted tribunal saves to Google Drive"""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        formatted_entry = f"\n\n> [UPDATE: {timestamp}]\n{content}"
        cloud.append_file(mission, filename, formatted_entry)

    def log_event(self, mission, role, text):
        """CLOUD OVERRIDE: Append chat logs directly to Google Drive"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_log = f"\n[{timestamp}] {role}: {text}"
        cloud.append_file(mission, "raw_logs.txt", formatted_log)

# ==========================================
# --- 3. THE INTERFACE ---
# ==========================================
st.set_page_config(page_title="Scribe Online Team Edition", layout="wide", page_icon="👽")
system = MissionControl()
system.load_css()

with st.sidebar:
    st.header("🔌 Cartridge Loader")
    if st.button("🔄 Scan / Patch Missions"):
        st.rerun()

    missions = system.get_missions()
    new_mission = st.text_input("New Mission Name:")

    if st.button("Initialize Cartridge"):
        if new_mission:
            system.create_mission(new_mission)
            st.rerun()

    selected_mission = st.selectbox("Active System:", missions, index=0 if missions else None)

    st.divider()

    if selected_mission:
        st.subheader("🚨 TRIBUNAL CONTROL")
        if st.button("FORCE FLUSH (Trigger Review)"):
            if "messages" in st.session_state:
                trigger_msg = "**[SYSTEM OVERRIDE]: FORCE FLUSH INITIATED. Stop. Review the logs. Find the most important unsaved insight. Present it for the Tribunal.**"
                st.session_state.messages.append({"role": "user", "content": trigger_msg})
                system.log_event(selected_mission, "SYSTEM", "FORCE FLUSH TRIGGERED")
                st.rerun()

    st.divider()

    st.subheader("⚙️ ENGINE CONTROL")
    ai_provider_choice = st.radio(
        "Active Intelligence Core:",
        [
            "Claude 4.6 Sonnet (Speed/Coding)", 
            "Gemini 3.1 Pro (Mega-Context)", 
            "Gemini 2.5 Flash (Fast/Cheap)"
        ],
        index=0 
    )
    st.divider()

    if selected_mission:
        st.caption(f"Mounted: {selected_mission}")
        with st.expander("View System Prompt"):
            st.text(system.read_file(selected_mission, "system_prompt.md"))

        # ==========================================
        # NEW FEATURE: 1-CLICK CONTEXT EXPORT
        # ==========================================
        st.divider()
        st.subheader("📋 CONTEXT EXPORT")
        raw_logs = system.read_file(selected_mission, "raw_logs.txt")

        # Corrected syntax: 'text' is the payload, the labels are separate!
        st_copy_to_clipboard(
            text=raw_logs, 
            before_copy_label="📋 Copy Full Context",
            after_copy_label="✅ Copied!"
        )

        # 👇 -------- PASTE THIS NEW PART RIGHT HERE -------- 👇
        st.subheader("📥 CONTEXT LOAD")
        if st.button("Load Full Context", use_container_width=True):
            # 1. Grab the raw logs
            full_logs = system.read_file(selected_mission, "raw_logs.txt")

            # 2. Inject them into the chat history
            st.session_state.messages.append({
                "role": "user", 
                "content": f"**[SYSTEM OVERRIDE: INJECTING FULL CONTEXT FROM RAW_LOGS.TXT]**\n\n{full_logs}"
            })

            # 3. Log the action and refresh
            system.log_event(selected_mission, "SYSTEM", "MANUAL CONTEXT INJECTION TRIGGERED")
            st.rerun()
        # 👆 ------------------------------------------------ 👆

if selected_mission:
    st.title(f"Scribe: {selected_mission}")

# --- MEMORY INIT ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "latest_audio" not in st.session_state:
    st.session_state.latest_audio = None
if "pasted_images" not in st.session_state:
    st.session_state.pasted_images = [] 
if "paste_key" not in st.session_state:
    st.session_state.paste_key = 0
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 100

# Render History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
#  UNIFIED INTELLIGENCE CENTER (DROP ZONE)
# ==========================================
st.markdown("---")

st.markdown("""
    <style>
    iframe[title="streamlit_paste_button.streamlit_paste_button"] {
        filter: invert(1);
    }
    </style>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 4])

with col1:
    paste_result = pbutton(
        label="📋 Paste Image",
        text_color="#000000",           
        background_color="#FFFFFF",     
        hover_background_color="#DDDDDD",
        key=f"paste_btn_{st.session_state.paste_key}",
    )

with col2:
    with st.expander("📂 Upload Evidence (Images or Text)", expanded=False):
        uploaded_files = st.file_uploader(
            "Drop mixed files here", 
            type=["png", "jpg", "jpeg", "txt", "md"], 
            accept_multiple_files=True,
            label_visibility="collapsed", 
            key=f"file_up_{st.session_state.uploader_key}"
        )

# 2. CAPTURE LOGIC
final_image_payload = []
text_payload_buffer = ""

if paste_result.image_data is not None:
    is_new = False
    if len(st.session_state.pasted_images) == 0:
        is_new = True
    else:
        last_img = st.session_state.pasted_images[-1]
        if paste_result.image_data.tobytes() != last_img.tobytes():
            is_new = True

    if is_new:
        st.session_state.pasted_images.append(paste_result.image_data)
        st.toast("Image captured!", icon="📸")

final_image_payload.extend(st.session_state.pasted_images)

if uploaded_files:
    for f in uploaded_files:
        if f.type and f.type.startswith("image"):
            final_image_payload.append(Image.open(f))
        else:
            raw_text = f.getvalue().decode("utf-8")
            text_payload_buffer += f"\n=== SOURCE: {f.name} ===\n{raw_text}\n***\n"

# 3. THE HUD (Display Staged Evidence)
if final_image_payload:
    st.caption(f"👁️ Visual Context Active: {len(final_image_payload)} images ready.")
    cols = st.columns(4)
    for i, img in enumerate(final_image_payload):
        with cols[i % 4]:
            st.image(img, width=100)

if text_payload_buffer:
    text_file_count = len([f for f in uploaded_files if not (f.type and f.type.startswith("image"))])
    st.caption(f"📚 Knowledge Context Active: {text_file_count} text files ready to ingest.")

# ==========================================
#  COMMAND INPUT
# ==========================================
if prompt := st.chat_input("Input command..."):
    
    full_prompt_package = prompt
    if text_payload_buffer:
        full_prompt_package += f"\n\n[SYSTEM: ATTACHED KNOWLEDGE BATCH]\n{text_payload_buffer}"
        st.toast("Sending text files to Brain...", icon="🚀")

    st.chat_message("user").markdown(prompt)

    if final_image_payload:
        for img in final_image_payload:
            st.chat_message("user").image(img, width=300)
        
        st.session_state.messages.append({"role": "user", "content": f"{prompt} \n\n*[{len(final_image_payload)} Images Attached]*"})
        system.log_event(selected_mission, "USER", f"{prompt} [IMAGES SENT]")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        system.log_event(selected_mission, "USER", prompt)

    st.session_state.latest_audio = None 

    sys_prompt = system.read_file(selected_mission, "system_prompt.md")
    bible = system.read_file(selected_mission, "project_bible.md")
    graveyard = system.read_file(selected_mission, "graveyard.md")
    system_instruction = f"{sys_prompt}\n\n=== BIBLE ===\n{bible}\n\n=== GRAVEYARD ===\n{graveyard}"

    try:
        # --- READ THE SIDEBAR TOGGLE ---
        if "Claude" in ai_provider_choice:
            selected_provider = "claude"
            active_model = "claude-sonnet-4-6"  # <--- UPDATED TO YOUR VALID MODEL
        elif "Flash" in ai_provider_choice:
            selected_provider = "gemini"
            active_model = "models/gemini-2.5-pro"
        else:
            selected_provider = "gemini"
            active_model = "gemini-3.1-pro-preview"

        # --- THE NEW ROUTER CALL ---
        ai_text_response = llm_router.generate_response(
            provider=selected_provider, # <--- DYNAMICALLY SET BY UI!
            model_name=active_model,
            system_instruction=system_instruction,
            chat_history=st.session_state.messages[:-1], 
            prompt_text=full_prompt_package,
            images=final_image_payload
        )

        autoplay_audio(ai_text_response) 
        st.session_state.messages.append({"role": "assistant", "content": ai_text_response})
        system.log_event(selected_mission, "AI", ai_text_response)

        # --- AUTO-CLEAR PROTOCOL ---
        st.session_state.pasted_images = []  
        st.session_state.paste_key += 1
        st.session_state.uploader_key += 1
        st.rerun()

    except Exception as e:
        st.error(f"Engine Failure: {e}")

# ==========================================
#  PERSISTENT DASHBOARD
# ==========================================
if st.session_state.latest_audio:
    with st.container():
        st.markdown("---") 
        st.markdown("**🔊 Mission Audio**")
        st.markdown(st.session_state.latest_audio, unsafe_allow_html=True)

if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
    last_response = st.session_state.messages[-1]["content"]
    cmd_pattern = r"### APPEND: (.*?)\n(.*?)(?=\n###|\Z)"
    match = re.search(cmd_pattern, last_response, re.DOTALL)

    if match:
        target_file = match.group(1).strip()
        payload = match.group(2).strip()
        with st.container():
            st.info(f"💾 TRIBUNAL: Ready to write to `{target_file}`")
            def execute_save():
                system.update_file(selected_mission, target_file, payload)
                system.log_event(selected_mission, "SYSTEM", f"Wrote to {target_file}")
            if st.button("CONFIRM WRITE", on_click=execute_save, key="persistent_save_final"):

                st.success("Memory Updated.")
