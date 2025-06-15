'''
Python script to automatically upload a file or all images in a folder to Google Drive using the Drive API.

Prerequisites:
1. Enable the Google Drive API in your Google Cloud Console.
2. Download your OAuth 2.0 Client credentials JSON and place it locally.
3. Install dependencies:
   ```bash
   pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
   ```

Usage:
- Provide `--local-path` (or `-l`) to specify a file or folder to upload.
- Optionally provide `--drive-folder-id` (or `-d`) for target Drive folder ID.
- Provide `--credentials` (or `-c`) to specify path to your credentials JSON (default: credentials.json).
- First run will open a browser for OAuth2 and save tokens in `<credentials>_token.pickle` next to the credentials file.
- Subsequent runs will reuse and auto-refresh tokens (no browser needed unless credentials change).
'''

import os
import pickle
import argparse
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these SCOPES, delete the token file
SCOPES = [
  'https://www.googleapis.com/auth/drive.file',
  'https://www.googleapis.com/auth/drive.readonly'
]
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}

def authenticate(credentials_path):
    """
    Authenticate using the given credentials JSON, saving and refreshing tokens as needed.
    """
    token_path = 'token.pickle'
    creds = None
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token_file:
            creds = pickle.load(token_file)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as token_file:
            pickle.dump(creds, token_file)
    return creds


def upload_file_to_drive(service, file_path, mime_type=None, parent_folder_id=None):
    """
    Upload a single file to Google Drive.
    Returns the uploaded file ID.
    """
    metadata = {'name': os.path.basename(file_path)}
    if parent_folder_id:
        metadata['parents'] = [parent_folder_id]

    media = MediaFileUpload(file_path, mimetype=mime_type)
    file = service.files().create(body=metadata, media_body=media, fields='id').execute()
    print(f"Uploaded '{file_path}' -> ID: {file.get('id')}")
    return file.get('id')


def upload_folder_to_drive(folder_path, credentials_path, parent_folder_id=None):
    """
    Upload all image files in a local folder to Google Drive.
    """
    creds = authenticate(credentials_path)
    service = build('drive', 'v3', credentials=creds)

    for entry in os.listdir(folder_path):
        full_path = os.path.join(folder_path, entry)
        _, ext = os.path.splitext(entry)
        if os.path.isfile(full_path) and ext.lower() in IMAGE_EXTENSIONS:
            upload_file_to_drive(service, full_path, parent_folder_id=parent_folder_id)


def main(local_path, credentials_path, parent_folder_id=None):
    """
    Determine if the local path is a file or folder and upload accordingly.
    """
    try:
        if os.path.isdir(local_path):
            print(f"Detected folder: {local_path}. Uploading all images inside...")
            upload_folder_to_drive(local_path, credentials_path, parent_folder_id)
        elif os.path.isfile(local_path):
            creds = authenticate(credentials_path)
            service = build('drive', 'v3', credentials=creds)
            upload_file_to_drive(service, local_path, parent_folder_id=parent_folder_id)
        else:
            print(f"Error: '{local_path}' is not a valid file or directory.")
    except FileNotFoundError as e:
        print(f"Error: {e}.\nPlease download your OAuth2 credentials JSON file from Google Cloud Console and place it at the specified path, or provide the correct path using the --credentials/-c option.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Upload a file or all images in a folder to Google Drive")
    parser.add_argument('-l', '--local-path', dest='local_path', required=True,
                        help='Local file or folder path to upload')
    parser.add_argument('-d', '--drive-folder-id', dest='drive_folder_id', default=None,
                        help='Google Drive folder ID to upload into')
    parser.add_argument('-c', '--credentials', dest='credentials_path', default='credentials.json',
                        help='Path to OAuth2 credentials JSON file')
    args = parser.parse_args()

    main(args.local_path, args.credentials_path, parent_folder_id=args.drive_folder_id)
