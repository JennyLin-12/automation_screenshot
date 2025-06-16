#!/usr/bin/env python3
import os
import json
import base64
import argparse
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}

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


def upload_file_to_drive(drive, file_path, mime_type=None, parent_folder_id=None):
    """上傳單一檔案到 Google Drive"""
    print(f"[Upload] 開始上傳檔案：{file_path}")
    metadata = {'name': os.path.basename(file_path)}
    if parent_folder_id:
        metadata['parents'] = [parent_folder_id]

    media = MediaFileUpload(file_path, mimetype=mime_type)
    try:
        file = drive.files().create(body=metadata, media_body=media, fields='id').execute()
        print(f"[Upload] ✅ 成功上傳 '{file_path}' → ID: {file.get('id')}")
        return file.get('id')
    except Exception as e:
        print(f"[Upload] ❌ 上傳失敗：{file_path}\n錯誤：{e}")
        return None


def upload_folder_to_drive(drive, folder_path, parent_folder_id=None):
    """上傳整個資料夾內所有圖片檔案"""
    print(f"[Upload] 掃描資料夾：{folder_path}")
    count = 0
    for entry in os.listdir(folder_path):
        full_path = os.path.join(folder_path, entry)
        _, ext = os.path.splitext(entry)
        if os.path.isfile(full_path) and ext.lower() in IMAGE_EXTENSIONS:
            upload_file_to_drive(drive, full_path, parent_folder_id=parent_folder_id)
            count += 1
    print(f"[Upload] 完成，共上傳 {count} 張圖片")


def main(args):
    print("[Main] 啟動 Google Drive 上傳工具")

    if args.token_base64:
        if os.path.exists('token.pickle'):
            print("[Main] 偵測到 token.pickle 已存在，跳過 base64 解碼覆蓋")
        else:
            print("[Main] 偵測到 base64 編碼的 token，解碼並寫入 token.pickle")
            token_bytes = base64.b64decode(args.token_base64)
            with open('token.pickle', 'wb') as f:
                f.write(token_bytes)

    # 認證
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
        print("[Main] ✅ 已建立 Google Drive client")
    except Exception as e:
        print(f"[Main] ❌ 建立 Drive client 失敗：{e}")
        return

    # 檔案或資料夾上傳
    if os.path.isdir(args.local_path):
        print(f"[Main] 偵測到資料夾：{args.local_path}，將上傳所有圖片")
        upload_folder_to_drive(drive, args.local_path, parent_folder_id=args.drive_folder_id)
    elif os.path.isfile(args.local_path):
        print(f"[Main] 偵測到單一檔案：{args.local_path}，開始上傳")
        upload_file_to_drive(drive, args.local_path, parent_folder_id=args.drive_folder_id)
    else:
        print(f"[Main] ❌ 錯誤：'{args.local_path}' 不是有效的檔案或資料夾")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Upload a file or all images in a folder to Google Drive")
    parser.add_argument('-j', '--credentials-json', required=True,
                        help="OAuth2 or service account JSON string")
    parser.add_argument('-l', '--local-path', dest='local_path', required=True,
                        help='Local file or folder path to upload')
    parser.add_argument('-f', '--drive-folder-id', dest='drive_folder_id', default=None,
                        help='Google Drive folder ID to upload into')
    parser.add_argument('--service-account', action='store_true',
                        help="Interpret credentials JSON as a service account key")
    parser.add_argument('--token-base64', default=None,
                        help="(Optional) Base64-encoded token.pickle content")
    args = parser.parse_args()
    main(args)
