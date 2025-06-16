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

SCOPES = [
  'https://www.googleapis.com/auth/drive.file',
  'https://www.googleapis.com/auth/drive.readonly'
]


def authenticate_oauth_from_json(credentials_json_str):
    """使用 OAuth2 客戶端憑證 JSON 字串"""
    print("[Auth] 使用 OAuth2 認證")
    creds = None
    token_path = 'token.pickle'
    if os.path.exists(token_path):
        print(f"[Auth] 發現 token.pickle，嘗試讀取")
        import pickle
        with open(token_path, 'rb') as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        print("[Auth] Token 無效或不存在，進行新授權流程")
        if creds and creds.expired and creds.refresh_token:
            print("[Auth] 嘗試使用 refresh token 更新")
            creds.refresh(Request())
        else:
            client_config = json.loads(credentials_json_str)
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as f:
            print("[Auth] 儲存新的 token 到 token.pickle")
            import pickle
            pickle.dump(creds, f)
    else:
        print("[Auth] 已成功使用現有 token")
    return creds


def authenticate_service_account_from_json(sa_key_json_str):
    """使用服務帳號金鑰 JSON 字串"""
    print("[Auth] 使用 Service Account 認證")
    key_info = json.loads(sa_key_json_str)
    creds = service_account.Credentials.from_service_account_info(
        key_info, scopes=SCOPES)
    return creds


def list_folder_files(drive, folder_id):
    """列出指定資料夾下所有未刪除檔案（不遞迴）"""
    print(f"[List] 取得資料夾內容：{folder_id}")
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
    print(f"[List] 找到 {len(files)} 個檔案")
    return files


def download_file(drive, file_id, file_name, dest_folder):
    """下載單一檔案到本地資料夾"""
    try:
        print(f"[Download] 準備下載：{file_name} (ID: {file_id})")
        request = drive.files().get_media(fileId=file_id)
        local_path = os.path.join(dest_folder, file_name)
        fh = io.FileIO(local_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  └▶ {file_name}: {int(status.progress() * 100)}%")
        fh.close()
        print(f"[Download] ✅ 已完成下載：{file_name}")
    except Exception as e:
        print(f"[Download] ❌ 下載失敗：{file_name}\n錯誤：{e}")


def main(args):
    print("[Main] 啟動 Google Drive 下載工具")

    # 如果提供了 base64 編碼的 token，先解碼寫入 token.pickle
    if args.token_base64:
        if os.path.exists('token.pickle'):
            print("[Main] 偵測到 token.pickle 已存在，跳過 base64 解碼覆蓋")
        else:
            print("[Main] 偵測到 base64 編碼的 token，解碼並寫入 token.pickle")
            token_bytes = base64.b64decode(args.token_base64)
            with open('token.pickle', 'wb') as f:
                f.write(token_bytes)

    # 選擇認證方式
    try:
        if args.service_account:
            creds = authenticate_service_account_from_json(args.credentials_json)
        else:
            creds = authenticate_oauth_from_json(args.credentials_json)
    except Exception as e:
        print(f"[Auth] ❌ 認證失敗：{e}")
        return

    try:
        drive = build('drive', 'v3', credentials=creds)
        print("[Main] ✅ 已建立 Drive client")
    except Exception as e:
        print(f"[Main] ❌ 建立 Drive client 失敗：{e}")
        return

    # 列出資料夾內容
    files = list_folder_files(drive, args.folder_id)
    for f in files:
        print(f" • {f['name']} ({f['mimeType']}) ← ID: {f['id']}")

    # 下載檔案（非資料夾）
    if args.download_to:
        print(f"[Main] 準備下載檔案至本地資料夾：{args.download_to}")
        os.makedirs(args.download_to, exist_ok=True)
        for f in files:
            if f['mimeType'] != 'application/vnd.google-apps.folder':
                download_file(drive, f['id'], f['name'], args.download_to)
        print("[Main] 所有檔案處理完成")


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
