#!/usr/bin/env python3
import os
import io
import argparse
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# OAuth2 或 Service Account 用到的 scope
SCOPES = [
  'https://www.googleapis.com/auth/drive.file',
  'https://www.googleapis.com/auth/drive.readonly'
]

def authenticate_oauth(credentials_path):
    """使用 OAuth2 用戶端憑證 (credentials.json)"""
    creds = None
    token_path = 'token.pickle'
    if os.path.exists(token_path):
        import pickle
        with open(token_path, 'rb') as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as f:
            import pickle
            pickle.dump(creds, f)
    return creds

def authenticate_service_account(sa_key_path):
    """使用服務帳號金鑰 JSON"""
    creds = service_account.Credentials.from_service_account_file(
        sa_key_path, scopes=SCOPES)
    return creds

def list_folder_files(drive, folder_id):
    """列出指定資料夾下所有未刪除檔案（不遞迴）"""
    query = f"'{folder_id}' in parents and trashed=false"
    files = []
    page_token = None
    while True:
        resp = drive.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(id, name, mimeType)',
            pageToken=page_token
        ).execute()
        files.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken', None)
        if not page_token:
            break
    return files

def download_file(drive, file_id, file_name, dest_folder):
    """下載單一檔案到本地資料夾"""
    request = drive.files().get_media(fileId=file_id)
    fh = io.FileIO(os.path.join(dest_folder, file_name), 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"Downloading {file_name}: {int(status.progress() * 100)}%")
    fh.close()

def main(args):
    # 選擇認證方式
    if args.service_account:
        creds = authenticate_service_account(args.credentials)
    else:
        creds = authenticate_oauth(args.credentials)

    drive = build('drive', 'v3', credentials=creds)

    # 列出檔案
    files = list_folder_files(drive, args.folder_id)
    print(f"Found {len(files)} files in folder {args.folder_id}:")
    for f in files:
        print(f" • {f['name']}  ({f['mimeType']})  ← ID: {f['id']}")

    # 如果有指定要下載，就依序抓下來
    if args.download_to:
        os.makedirs(args.download_to, exist_ok=True)
        for f in files:
            # 只有非資料夾才下載
            if f['mimeType'] != 'application/vnd.google-apps.folder':
                download_file(drive, f['id'], f['name'], args.download_to)

if __name__ == '__main__':
    p = argparse.ArgumentParser(
        description="List (and optionally download) all files in a Google Drive folder.")
    p.add_argument('-c', '--credentials', required=True,
                   help="Path to OAuth2 credentials.json or service account JSON")
    p.add_argument('-f', '--folder-id', required=True,
                   help="Google Drive Folder ID to list files from")
    p.add_argument('-d', '--download-to', default=None,
                   help="(Optional) Local folder to download all files into")
    p.add_argument('--service-account', action='store_true',
                   help="Use service account JSON instead of user OAuth2")
    args = p.parse_args()
    main(args)
