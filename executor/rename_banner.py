import os
import cv2
import shutil
import subprocess
from datetime import datetime
import pytz
import re

# === 參數設定 ===
# 取得這支 script 的資料夾
script_dir = os.path.dirname(os.path.abspath(__file__))
# 往上回到 project_root 再進入 icons
ICONS_DIR    = os.path.join(script_dir, '..', 'icons')           # icon 資料夾
BANNERS_DIR  = os.path.join(script_dir, '..', 'banners')         # 原始大圖資料夾
OUTPUT_DIR   = os.path.join(script_dir, '..', 'rename_banners')  # 處理後輸出資料夾
CROP_SCRIPT  = os.path.join(script_dir, 'crop_icon.py')          # 你的裁切腳本

THRESHOLD    = 0.95                                              # matchTemplate 相似度門檻

# 確保輸出資料夾存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1) 載入所有 icon
icons = []
for fn in os.listdir(ICONS_DIR):
    if fn.lower().endswith(('.png','.jpg','.jpeg')):
        path = os.path.join(ICONS_DIR, fn)
        icon = cv2.imread(path, cv2.IMREAD_COLOR)
        if icon is not None:
            name, _ = os.path.splitext(fn)
            icons.append((name, icon))
print(f"[INFO] 載入 icons：{[n for n,_ in icons]}")

index = 0
# 2) 逐張處理 banner
for fn in sorted(os.listdir(BANNERS_DIR)):
    index += 1
    if not fn.lower().endswith(('.png','.jpg','.jpeg')):
        continue

    banner_path = os.path.join(BANNERS_DIR, fn)
    img = cv2.imread(banner_path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"[WARN] 讀取失敗：{fn}")
        continue

    best_name  = None
    best_score = -1.0

    # 3) template matching
    for name, icon in icons:
        ih, iw = icon.shape[:2]
        h, w   = img.shape[:2]
        if ih > h or iw > w:
            continue

        res = cv2.matchTemplate(img, icon, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        print(f"[DEBUG] {fn} vs {name}: score={max_val:.4f}")

        if max_val > best_score:
            best_score = max_val
            best_name  = name

    # 取得副檔名
    _, ext = os.path.splitext(fn)

    # 指定時區名稱（例：Asia/Taipei）
    tz = pytz.timezone("Asia/Taipei")

    # 取得現在時間（含指定時區）
    now = datetime.now(tz)
    
    # 取得當前日期字串 (YYYY_MMDD)
    date_str = now.strftime("%Y_%m%d")

    # 4a) match 成功 → 複製並改名
    if best_score >= THRESHOLD:
        m = re.match(r'^(.+)_\d+$', best_name)
        if m:
            best_name = m.group(1)
            
        new_fn = f"{date_str}_web_banner_{best_name}{ext}"
        print(f"[MATCH] {fn} → {new_fn} (score={best_score:.4f})")
        shutil.copy(banner_path, os.path.join(OUTPUT_DIR, new_fn))

    # 4b) match 失敗 → 改名不包含品牌，複製原檔並呼叫 crop_icon.py
    else:
        new_fn = f"{date_str}_web_banner_{index}{ext}"
        print(f"[NO MATCH] {fn} → {new_fn} (best={best_name}, score={best_score:.4f})")
        # 先把原 banner 複製到 OUTPUT_DIR
        shutil.copy(banner_path, os.path.join(OUTPUT_DIR, new_fn))

        # 再用 subprocess 呼叫 crop_icon.py
        cmd = ['python', CROP_SCRIPT, banner_path]

        print(f"[CROP-START] 呼叫裁切腳本：{' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
            print(f"[CROP-DONE] {fn} 已裁切 icon 到 {OUTPUT_DIR}")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] 裁切失敗：{e}")

print("\n所有處理完成，請至 rename_banners 檢查結果！")
