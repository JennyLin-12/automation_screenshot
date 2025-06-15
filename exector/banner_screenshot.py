# screenshot.py
import asyncio
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

async def take_screenshots():
    print("[Screenshot] 啟動 Playwright 自動化")
    async with async_playwright() as p:
        # 執行登入
        page = await launch_and_login()
        print("[Screenshot] 登入完成，開始截圖流程。")
        
        await page.set_viewport_size({"width": 1280, "height": 800})
        print("[Screenshot] 已設定視窗大小為 1280x800")

        # 前往首頁並等待 carousel 容器出現
        await page.goto(HOME_URL)
        await page.wait_for_selector('.carousel-container', timeout=60000)
        print(f"[Screenshot] 已導航至 {HOME_URL} 並偵測到 carousel-container")

                # 定位第一個 carousel-container
        wrapper = page.locator('.carousel-container').first
        print("[Screenshot] 定位 carousel-container 區塊")

        # 從 HTML 結構中計算輪播內的圖片數量
        img_count = await wrapper.locator('img').count()
        print(f"[Screenshot] 輪播中共偵測到 {img_count} 張圖片")
        
        await page.wait_for_timeout(500)

        # 依照圖片數進行截圖，等候自動輪播切換
        for idx in range(img_count):
            if idx > 0:
                print(f"[Screenshot] 等待自動輪播切換 ({ROTATION_INTERVAL}ms)")
                await page.wait_for_timeout(ROTATION_INTERVAL)
            filename = os.path.join(OUTPUT_DIR, f"banner_{idx+1}.png")
            print(f"[Screenshot] 截圖第 {idx+1} 張圖片: {filename}")
            await page.screenshot(path=filename)

        # 關閉瀏覽器
        await page.context.close()
        print("[Screenshot] 截圖流程結束，瀏覽器已關閉。")

if __name__ == '__main__':
    asyncio.run(take_screenshots())
