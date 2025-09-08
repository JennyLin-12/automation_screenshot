# screenshot.py
import asyncio
import argparse
import os
from playwright.async_api import async_playwright
from login import launch_and_login, HOME_URL
from observe_banner_rotations import observe_banner_rotations
from datetime import datetime

# 取得這支 script 的資料夾
script_dir = os.path.dirname(os.path.abspath(__file__))
# 圖片儲存資料夾
OUTPUT_DIR = os.path.join(script_dir, '..', 'banners')
# 每次輪播切換等待時間 (毫秒)
ROTATION_INTERVAL = 3000
# 最多截圖張數（避免無限）
MAX_SLIDES = 50

async def take_screenshots(email: str, password: str):
    print("[Screenshot] 啟動 Playwright 自動化")
    async with async_playwright() as p:
        # 登入
        page = await launch_and_login(email=email, password=password)
        print("[Screenshot] 登入完成，開始截圖流程。")

        await page.set_viewport_size({"width": 1280, "height": 800})
        print("[Screenshot] 已設定視窗大小為 1280x800")

        await page.goto(HOME_URL)
        await page.wait_for_selector('.carousel-container', timeout=10000)
        print(f"[Screenshot] 已導航至 {HOME_URL} 並偵測到 carousel-container")

        await page.wait_for_timeout(2000)

        selector = (
            'div.bg_sbds-background-color-dark'
            '.h_0'
            '.transition_height_0\\.3s'
        )
        if await page.is_visible(selector, timeout=1000):
            print("[Screenshot] 偵測 Header 中存在 ShopBack Extension")
            y_offset = 64
        else:
            print("[Screenshot] 偵測 Header 中沒有 ShopBack Extension")
            y_offset = 0

        # 計算輪播張數
        wrapper = page.locator('.carousel-container').first
        img_count = await wrapper.locator('> div[data-ui-element-name="hero banner"]').count()
        print(f"[Screenshot] 輪播中共偵測到 {img_count} 個 banner 項目")

        # 定義 callback：每次切換完成就截圖
        async def on_switch(call_index: int, current_index: int):
            filename = os.path.join(OUTPUT_DIR, f"banner_{call_index}.png")
            print(f"[Screenshot] 觸發第 {call_index} 次（索引 {current_index}）→ 截圖：{filename}")
            await page.screenshot(path=filename, clip={
                "x": 0,
                "y": y_offset,
                "width": await page.evaluate("() => window.innerWidth"),
                "height": (await page.evaluate("() => window.innerHeight")) - y_offset
            })

        # 觀察並觸發截圖：
        # - include_initial=True：先對目前第一張也截 1 次
        # - max_switches=img_count：總共觸發 img_count 次（含第一張）
        await observe_banner_rotations(
            page,
            on_switch,
            max_switches=img_count,
            include_initial=True,
            stable_frames=10,
            velocity_eps=0.5,
        )

        await page.context.close()
        print("[Screenshot] 截圖流程結束，瀏覽器已關閉。")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Screenshot banners")
    parser.add_argument('-a', '--account', required=True, help='ShopBack login email')
    parser.add_argument('-p', '--password', required=True, help='ShopBack login password')
    args = parser.parse_args()
        
    asyncio.run(take_screenshots(email=args.account, password=args.password))
