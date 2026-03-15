import os
import json
import io
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

load_dotenv()

class CloudEngine:

    def setup_memory_sheet(self, mission_name):
        """Finds or creates the scribe_memory sheet for a specific mission."""
        mission_id = self._get_folder_id(mission_name, self.root_folder_id)
        if not mission_id:
            return None

        sheet_name = "scribe_memory"
        existing_id = self._get_file_id(sheet_name, mission_id)

        if existing_id:
            return existing_id # Sheet already exists, return its ID

        # Create a new Google Sheet inside the specific Mission Folder
        file_metadata = {
            'name': sheet_name,
            'mimeType': 'application/vnd.google-apps.spreadsheet',
            'parents': [mission_id]
        }
        sheet_file = self.service.files().create(body=file_metadata, fields='id').execute()
        sheet_id = sheet_file.get('id')

        # Format the 9 Core Column Headers (Added Mastery_Score & Rep_Count)
        headers = [["Timestamp", "Source", "Raw_Text", "Category", "Keywords", "Summary", "Chunk_Index", "Mastery_Score", "Rep_Count"]]
        body = {'values': headers}

        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range="A1:I1", # <--- Updated to I1
            valueInputOption="USER_ENTERED", body=body
        ).execute()

        print(f"📊 [CLOUD] Built Spreadsheet Brain for: {mission_name}")
        return sheet_id

    def __init__(self):
        self.delegated_email = os.getenv("GOOGLE_DRIVE_DELEGATED_EMAIL")
        self.root_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        scopes = ['https://www.googleapis.com/auth/drive']

        # 1. ADD THE SHEETS SCOPE HERE 👇
        scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]

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

        # 👇 ADD THIS MISSING LINE FOR SHEETS 👇
        self.sheets_service = build('sheets', 'v4', credentials=delegated_creds)

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

    def append_sheet_row(self, sheet_id, row_data):
        """Appends a single row to the bottom of the Google Sheet."""
        body = {'values': [row_data]}
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="A:I", # <--- Expanded to column I
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()

    def get_last_processed_chunk(self, sheet_id):
        """Reads the bottom row of the sheet to find the last processed text."""
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="A:I" # <--- Expanded to column I
        ).execute()

        values = result.get('values', [])
        if len(values) <= 1:
            return None 

        return values[-1][2] 

    def get_all_sheet_rows(self, sheet_id):
        """Downloads the entire spreadsheet into a list of rows."""
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="A:I" # <--- Expanded to column I
        ).execute()

        rows = result.get('values', [])

        # --- BULLETPROOF PADDING FIX ---
        if rows:
            expected_length = len(rows[0])
            for row in rows:
                while len(row) < expected_length:
                    row.append("")

        return rows

    def update_chunk_score(self, sheet_id, chunk_index, score, new_reps):
        """Writes the Mastery Score and Rep Count to Columns H and I for a specific chunk."""
        # Math: Index 0 is under the headers, so it's Row 2!
        sheet_row = int(chunk_index) + 2  
        range_name = f"H{sheet_row}:I{sheet_row}"
        body = {'values': [[score, new_reps]]}

        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=range_name,
            valueInputOption="USER_ENTERED", body=body
        ).execute()

# ==========================================
# QUICK TEST 
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