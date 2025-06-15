#!/usr/bin/env python3
import os
import io
import argparse
import json
import base64
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

def authenticate_oauth_from_json(credentials_json_str):
    """使用 OAuth2 客戶端憑證 JSON 字串"""
    creds = None
    token_path = 'token.pickle'
    # 如果有提前提供的 base64 token，已寫入 token.pickle
    if os.path.exists(token_path):
        import pickle
        with open(token_path, 'rb') as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = json.loads(credentials_json_str)
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
        # 保存新的 token
        with open(token_path, 'wb') as f:
            import pickle
            pickle.dump(creds, f)
    return creds


def authenticate_service_account_from_json(sa_key_json_str):
    """使用服務帳號金鑰 JSON 字串"""
    key_info = json.loads(sa_key_json_str)
    creds = service_account.Credentials.from_service_account_info(
        key_info, scopes=SCOPES)
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
    # 如果提供了 base64 編碼的 token，先解碼寫入 token.pickle
    if args.token_base64:
        token_bytes = base64.b64decode(args.token_base64)
        with open('token.pickle', 'wb') as f:
            f.write(token_bytes)

    # 選擇認證方式：直接使用 JSON 字串
    if args.service_account:
        creds = authenticate_service_account_from_json(args.credentials_json)
    else:
        creds = authenticate_oauth_from_json(args.credentials_json)

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
        description="List (and optionally download) all files in a Google Drive folder using JSON credentials.")
    p.add_argument('-j', '--credentials-json', required=True,
                   help="OAuth2 or service account JSON string")
    p.add_argument('-f', '--folder-id', required=True,
                   help="Google Drive Folder ID to list files from")
    p.add_argument('-d', '--download-to', default=None,
                   help="(Optional) Local folder to download all files into")
    p.add_argument('--service-account', action='store_true',
                   help="Interpret credentials JSON as a service account key")
    p.add_argument('--token-base64', default=None,
                   help="(Optional) Base64-encoded token.pickle content")
    args = p.parse_args()
    main(args)
