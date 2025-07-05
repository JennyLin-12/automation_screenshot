# screenshot.py
import asyncio
import argparse
import os
from playwright.async_api import async_playwright
from login import launch_and_login, HOME_URL

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
        # 執行登入
        page = await launch_and_login(email=email, password=password)
        print("[Screenshot] 登入完成，開始截圖流程。")
        
        await page.set_viewport_size({"width": 1280, "height": 800})
        print("[Screenshot] 已設定視窗大小為 1280x800")

        # 前往首頁並等待 carousel 容器出現
        await page.goto(HOME_URL)
        await page.wait_for_selector('.carousel-container', timeout=10000)
        print(f"[Screenshot] 已導航至 {HOME_URL} 並偵測到 carousel-container")
        
        await page.wait_for_timeout(500)
        
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

        # 定位第一個 carousel-container
        wrapper = page.locator('.carousel-container').first
        print("[Screenshot] 定位 carousel-container 區塊")

        # 計算輪播項目的數量（每個 banner 一個 div）
        img_count = await wrapper.locator('> div[data-ui-element-name="hero banner"]').count()
        print(f"[Screenshot] 輪播中共偵測到 {img_count} 個 banner 項目")

        # 依照圖片數進行截圖，等候自動輪播切換
        for idx in range(img_count):
            if idx > 0:
                print(f"[Screenshot] 等待自動輪播切換 ({ROTATION_INTERVAL}ms)")
                await page.wait_for_timeout(ROTATION_INTERVAL)
            filename = os.path.join(OUTPUT_DIR, f"banner_{idx+1}.png")
            print(f"[Screenshot] 截圖第 {idx+1} 張圖片: {filename}")
            await page.screenshot(path=filename, clip={
                "x": 0,
                "y": y_offset,
                "width": await page.evaluate("() => window.innerWidth"),
                "height": await page.evaluate("() => window.innerHeight") - y_offset
            })

        # 關閉瀏覽器
        await page.context.close()
        print("[Screenshot] 截圖流程結束，瀏覽器已關閉。")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Screenshot banners")
    parser.add_argument('-a', '--account', required=True, help='ShopBack login email')
    parser.add_argument('-p', '--password', required=True, help='ShopBack login password')
    args = parser.parse_args()
        
    asyncio.run(take_screenshots(email=args.account, password=args.password))
