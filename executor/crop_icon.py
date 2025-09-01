import os
import argparse
from PIL import Image

# 這支腳本用來裁切單張大圖中的 icon
# 圖片路徑由參數輸入，其餘裁切參數作為常數定義

# === 常數設定 ===
# 取得這支 script 的資料夾
script_dir = os.path.dirname(os.path.abspath(__file__))
DST_DIR    = os.path.join(script_dir, '..', 'unknow_icons')  # 裁切後 icon 存放資料夾

# 建立輸出資料夾（若不存在）
os.makedirs(DST_DIR, exist_ok=True)

def main():
    parser = argparse.ArgumentParser(
        description='裁切單張 banner 圖片的 icon 並輸出'
    )
    parser.add_argument(
        'input_image',
        help='待裁切的大圖檔案路徑'
    )
    parser.add_argument('--crop-x', type=int, default=165, help='裁切框 X 起始座標 (default: 165)')
    parser.add_argument('--crop-y', type=int, default=185, help='裁切框 Y 起始座標 (default: 185)')
    parser.add_argument('--crop-w', type=int, default=170, help='裁切框寬度 (default: 170)')
    parser.add_argument('--crop-h', type=int, default=56,  help='裁切框高度 (default: 56)')

    args = parser.parse_args()

    input_path = args.input_image

    # 打開圖片並裁切
    try:
        img = Image.open(input_path)
    except Exception as e:
        print(f"[ERROR] 無法開啟圖片：{input_path}, {e}")
        return

    box = (args.crop_x, args.crop_y, args.crop_x + args.crop_w, args.crop_y + args.crop_h)
    cropped = img.crop(box)

    # 輸出檔名加上 _icon
    base, ext = os.path.splitext(os.path.basename(input_path))
    new_name = f"{base}_icon{ext}"
    dst_path = os.path.join(DST_DIR, new_name)

    try:
        cropped.save(dst_path)
        print(f"[OK] 已裁切並儲存：{new_name}")
    except Exception as e:
        print(f"[ERROR] 無法儲存裁切檔案：{new_name}, {e}")

if __name__ == '__main__':
    main()
