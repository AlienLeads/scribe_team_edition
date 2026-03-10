import os
import json
import io
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

load_dotenv()

class CloudEngine:
    def __init__(self):
        self.delegated_email = os.getenv("GOOGLE_DRIVE_DELEGATED_EMAIL")
        self.root_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        scopes = ['https://www.googleapis.com/auth/drive']

        # --- THE RAILWAY SECRETS HACK ---
        google_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON")

        if google_json_env:
            # We are on Railway: Read the JSON string from the environment variable
            creds_dict = json.loads(google_json_env)
            creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            # We are on Local Laptop: Read the physical credentials.json file
            self.cred_file = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
            creds = service_account.Credentials.from_service_account_file(self.cred_file, scopes=scopes)

        delegated_creds = creds.with_subject(self.delegated_email)
        self.service = build('drive', 'v3', credentials=delegated_creds)

    def _get_folder_id(self, folder_name, parent_id):
        """Helper: Finds a folder ID by name inside a parent folder."""
        query = f"'{parent_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        return items[0]['id'] if items else None

    def _get_file_id(self, file_name, parent_folder_id):
        """Helper: Finds a file ID by name inside a specific folder."""
        query = f"'{parent_folder_id}' in parents and name='{file_name}' and mimeType!='application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        return items[0]['id'] if items else None

    def get_missions(self):
        """Job 1: Returns a list of all mission folder names in the Cortex Root."""
        query = f"'{self.root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        return [item['name'] for item in results.get('files', [])]

    def create_mission(self, mission_name):
        """Job 2: Creates a new mission folder and the 4 default files."""
        if self._get_folder_id(mission_name, self.root_folder_id):
            return  # Folder already exists

        # 1. Create Folder
        folder_metadata = {
            'name': mission_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [self.root_folder_id]
        }
        folder = self.service.files().create(body=folder_metadata, fields='id').execute()
        mission_id = folder.get('id')

        # 2. Load the REAL System Prompt (Bulletproof Path)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        master_path = os.path.join(script_dir, "MASTER_SYSTEM_PROMPT.md")

        sys_prompt_text = "System Prompt Missing."
        if os.path.exists(master_path):
            with open(master_path, "r", encoding="utf-8") as f:
                sys_prompt_text = f.read()

        # 3. Create the 4 Default Starter Files
        starter_files = {
            "system_prompt.md": sys_prompt_text,
            "project_bible.md": "# PROJECT BIBLE\n* [Source: GENESIS] Mission initialized.",
            "graveyard.md": "# GRAVEYARD\n* [Source: GENESIS] No bad ideas yet.",
            "raw_logs.txt": "--- MISSION START ---"
        }

        for filename, content in starter_files.items():
            media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain', resumable=True)
            file_metadata = {'name': filename, 'parents': [mission_id]}
            self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        print(f"📁 [CLOUD] Initialized Cartridge: {mission_name}")

    def read_file(self, mission_name, file_name):
        """Job 3: Reads the exact text from a cloud file (for prompt injection & copy button)."""
        mission_id = self._get_folder_id(mission_name, self.root_folder_id)
        if not mission_id:
            return "[MISSION NOT FOUND IN CLOUD]"

        file_id = self._get_file_id(file_name, mission_id)
        if not file_id:
            return "[FILE NOT FOUND IN CLOUD]"

        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

        return fh.getvalue().decode('utf-8')

    def append_file(self, mission_name, file_name, new_content):
        """Job 4: Appends new text to the bottom of a cloud file."""
        mission_id = self._get_folder_id(mission_name, self.root_folder_id)
        if not mission_id:
            return

        file_id = self._get_file_id(file_name, mission_id)
        if not file_id:
            return

        # 1. Download current content
        current_content = self.read_file(mission_name, file_name)

        # 2. Add new content to the bottom
        updated_content = current_content + new_content

        # 3. Upload it back
        media = MediaIoBaseUpload(io.BytesIO(updated_content.encode('utf-8')), mimetype='text/plain', resumable=True)
        self.service.files().update(fileId=file_id, media_body=media).execute()

# ==========================================
# QUICK TEST (Runs only if you execute this file directly)
# ==========================================
if __name__ == "__main__":
    print("Initializing Cloud Engine...")
    cloud = CloudEngine()

    print("Testing Cartridge Initialization...")
    cloud.create_mission("Cloud_Test_Alpha")

    print("Testing File Read...")
    bible_text = cloud.read_file("Cloud_Test_Alpha", "project_bible.md")
    print(f"BIBLE SAYS: {bible_text}")

    print("Testing File Append...")
    cloud.append_file("Cloud_Test_Alpha", "raw_logs.txt", "\n[TEST] We are live in the cloud!")

    print("SUCCESS! Go check your Google Drive!")