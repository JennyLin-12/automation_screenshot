import os
import time
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright

# 取得這支 script 的資料夾
script_dir = os.path.dirname(os.path.abspath(__file__))
# 圖片儲存資料夾
OUTPUT_DIR = os.path.join(script_dir, '..', 'full_page_screenshot')

def capture_full_page_with_playwright(
    url: str,
    output_name: str,
    scroll_pause: float = 2.0
):
    # 1. 產生日期字串 yyyy_mmdd
    date_str = datetime.now().strftime("%Y_%m%d")
    # 2. 組成檔名
    filename = f"{date_str}_{output_name}.png"
    output_path = f"{OUTPUT_DIR}/{filename}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        time.sleep(scroll_pause)

        prev_height = page.evaluate("() => document.body.scrollHeight")

        while True:
            page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(scroll_pause)
            new_height = page.evaluate("() => document.body.scrollHeight")
            if new_height == prev_height:
                break
            prev_height = new_height

        # 取得整個文件高度
        total_height = page.evaluate("() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
        # 設定 viewport 高度
        page.set_viewport_size({"width": 1920, "height": total_height})

        # full_page=True 會自動把整頁延展到 screenshot
        page.screenshot(path=output_path, full_page=True)
        print(f"Saved full-page screenshot to {output_path}")

        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="用 Playwright 截取整頁並自動滾動 (full-page screenshot)"
    )
    parser.add_argument('-u', '--url', required=True, help='要截圖的頁面 URL')
    parser.add_argument('-n', '--output_name', required=True, help='自訂輸出檔名前綴 (會套入 yyyy_mmdd_... page_Travel.png)')
    args = parser.parse_args()
    
    capture_full_page_with_playwright(
        url=args.url,
        output_name=args.output_name
    )
