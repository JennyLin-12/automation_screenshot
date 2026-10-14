# screenshot.py
# -*- coding: utf-8 -*-
import asyncio
import argparse
import os

from login import launch_and_login, HOME_URL
from banner_capture import capture_banners, HERO_SELECTOR

# 取得這支 script 的資料夾
script_dir = os.path.dirname(os.path.abspath(__file__))
# 圖片儲存資料夾
OUTPUT_DIR = os.path.join(script_dir, '..', 'banners')

# =========================
# 主流程
# =========================

async def take_screenshots(email: str, password: str):
    print("[Screenshot] 啟動 Playwright 自動化")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    async with launch_and_login(email=email, password=password) as page:
        print("[Screenshot] 登入完成，開始截圖流程。")

        await page.set_viewport_size({"width": 1280, "height": 800})
        print("[Screenshot] 已設定視窗大小為 1280x800")

        # 導航 & 等待基礎載入
        await page.goto(HOME_URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except:
            pass

        await page.wait_for_selector(HERO_SELECTOR, state="attached", timeout=20000)

        # 計算 Y 偏移（是否有 Extension 版頭）
        selector = (
            'div.bg_sbds-background-color-dark'
            '.h_0'
            '.transition_height_0\\.3s'
        )
        try:
            has_ext_header = await page.is_visible(selector, timeout=1000)
        except:
            has_ext_header = False
        y_offset = 64 if has_ext_header else 0
        print(f"[Screenshot] y_offset = {y_offset}")

        await capture_banners(page, OUTPUT_DIR, y_offset=y_offset)

    print("[Screenshot] 截圖流程結束，瀏覽器已關閉。")

# =========================
# 入口
# =========================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Screenshot banners")
    parser.add_argument('-a', '--account', required=True, help='ShopBack login email')
    parser.add_argument('-p', '--password', required=True, help='ShopBack login password')
    args = parser.parse_args()

    asyncio.run(take_screenshots(email=args.account, password=args.password))
