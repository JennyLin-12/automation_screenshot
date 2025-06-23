import os
import time
import asyncio
import argparse
from datetime import datetime
import pytz
from playwright.async_api import async_playwright
from login import launch_and_login, HOME_URL

# 取得這支 script 的資料夾
script_dir = os.path.dirname(os.path.abspath(__file__))
# 圖片儲存資料夾
OUTPUT_DIR = os.path.join(script_dir, '..', 'rewards_section_screenshot')

async def capture_rewards_section(email: str, password: str):
    # 1. 產生日期字串 yyyy_mmdd
    
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)
    date_str = now.strftime("%Y_%m%d")
    
    filename = f"{date_str}_top deal.png"
    output_path = f"{OUTPUT_DIR}/{filename}"

    async with async_playwright() as p:
        page = await launch_and_login(email=email, password=password)
        print("[Screenshot] 登入完成，開始截圖流程。")
        
        await page.set_viewport_size({"width": 1280, "height": 800})
        print("[Screenshot] 已設定視窗大小為 1280x800")

        # 導航到目標頁面，並等待網路空閒
        await page.goto("https://www.shopback.com.tw/", timeout=10000)
        print("網頁載入中，等待 networkidle 狀態")
        await page.wait_for_url("https://www.shopback.com.tw/", timeout=10000)

        # 定位到「旅費通通變回饋」區塊
        print("定位「旅費通通變回饋」區塊")
        selector = 'h3:has-text("旅費通通變回饋")'
        for _ in range(10):
            if await page.locator(selector).count() > 0:
                break
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(1)
        await page.wait_for_selector(selector, timeout=5000)
        
        selector = 'div.d_flex.flex_column.gap_16:has-text("旅費通通變回饋")'
        section = page.locator(selector)
        await section.wait_for(state="visible", timeout=20000)
        print("找到「旅費通通變回饋」區塊")
        
        # 顯式滾動到畫面中央
        print("將目標區塊捲動到畫面中央")
        await section.evaluate(
            """el => {
                // 找到 header 並取得高度
                const header = document.querySelector('header');
                const headerHeight = header ? header.offsetHeight : 0;
                // 計算元素在整頁的絕對 Y 座標，扣掉 headerHeight
                const absoluteY = el.getBoundingClientRect().top + window.scrollY - headerHeight;
                // 滾動到那個 Y 值
                window.scrollTo({ top: absoluteY, behavior: 'auto' });
            }"""
        )
        
        await asyncio.sleep(2)

        # 截圖並儲存
        await page.screenshot(path=output_path, full_page=False)
        print(f"已將區塊截圖並儲存為：{output_path}")

        # 關閉瀏覽器
        await page.context.close()
        print("瀏覽器已關閉，程式結束")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Screenshot reward section")
    parser.add_argument('-a', '--account', required=True, help='ShopBack login email')
    parser.add_argument('-p', '--password', required=True, help='ShopBack login password')
    args = parser.parse_args()
        
    asyncio.run(capture_rewards_section(email=args.account, password=args.password))
