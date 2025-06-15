import os
import asyncio
import argparse
from playwright.async_api import async_playwright, Page, BrowserContext

# 常數設定
LOGIN_URL = "https://www.shopback.com.tw/login?redirect=%2Faccount%2Flogin"
HOME_URL = "https://www.shopback.com.tw/"

# Persistent Context 資料夾路徑
script_dir = os.path.dirname(os.path.abspath(__file__))
DST_DIR    = os.path.join(script_dir, '..', 'user_data')
USER_DATA_DIR = os.getenv("PLAYWRIGHT_USER_DATA", DST_DIR)

async def is_logged_in(page: Page) -> bool:
    """
    檢查是否已登入：假設 page 已在首頁，只檢查「登入」按鈕是否存在
    """
    return not await page.is_visible("text=登入")

async def login_if_needed(context: BrowserContext, email: str, password: str) -> Page:
    """
    如未登入則執行多步驟登入，並將狀態保留在 Persistent Context
    回傳已登入的 Page 物件。
    """
    if not email or not password:
        raise ValueError("必須提供 email 及 password，請使用 -a 和 -p 提供")

    page = await context.new_page()
    await page.goto(HOME_URL, wait_until="networkidle")

    if await is_logged_in(page):
        print("已登入，跳過流程。")
        return page

    print("未登入，開始登入...")
    await page.goto(LOGIN_URL, wait_until="networkidle")

    # 輸入 Email 並提交
    await page.wait_for_selector('input[type="email"]', timeout=60000)
    await page.fill('input[type="email"]', email)
    await page.press('input[type="email"]', 'Enter')
    print("Email 已輸入，提交。")

    # 輸入 Password 並點擊登入
    await page.wait_for_selector('input[type="password"]', timeout=60000)
    await page.fill('input[type="password"]', password)
    await page.click('button:has-text("登入")')
    print("Password 已輸入，提交登入表單。")

    # 等待首頁載入完成
    await page.wait_for_url(HOME_URL, timeout=60000)
    if not await is_logged_in(page):
        raise RuntimeError("登入失敗：未偵測到登入狀態。")

    print("登入成功，Persistent Context 已更新。")
    return page

async def launch_and_login(email: str, password: str) -> Page:
    """
    啟動 Persistent Context 並嘗試登入，回傳已登入的 Page

    使用示例：
        python login.py -a user@example.com -p secret
    """
    # 確保 user_data 目錄存在
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    playwright = await async_playwright().start()
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False
    )
    # 關閉預設空白分頁
    for p in list(context.pages):
        if p.url == "about:blank":
            await p.close()

    page = await login_if_needed(context, email, password)
    return page

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch Playwright with persistent login.")
    parser.add_argument('-a', '--account', required=True, help='ShopBack login email')
    parser.add_argument('-p', '--password', required=True, help='ShopBack login password')
    args = parser.parse_args()

    page = asyncio.run(launch_and_login(email=args.account, password=args.password))
    # 此處可加入自動化後續流程，例如：
    # asyncio.run(take_screenshots(page))
