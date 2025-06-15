import os
import asyncio
import argparse
from playwright.async_api import async_playwright, Page, BrowserContext

# 常數設定
LOGIN_URL = "https://www.shopback.com.tw/login"
HOME_URL = "https://www.shopback.com.tw"

# 資料夾路徑與檔案設定
script_dir = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(script_dir, '..', 'state.json')

async def is_logged_in(page: Page) -> bool:
    """
    檢查是否已登入：假設 page 已在首頁，只檢查「登入」按鈕是否存在
    """
    return not await page.is_visible("text=登入")

async def login_if_needed(context: BrowserContext, email: str, password: str) -> tuple[Page, bool]:
    """
    如未登入則執行多步驟登入，並將狀態保留在 Persistent Context
    回傳已登入的 Page 物件。
    """
    if not email or not password:
        raise ValueError("必須提供 email 及 password，請使用 -a 和 -p 提供")
    page = await context.new_page()
    await page.goto(HOME_URL, wait_until="load", timeout=10000)

    print("🔐 未登入，開始登入...")
    if await is_logged_in(page):
        print("✅ 已登入，跳過登入流程。")
        return page, False

    print("🔐 未登入，開始登入...")
    await page.goto(LOGIN_URL, wait_until="networkidle")
    # 輸入 Email
    await page.wait_for_selector('input[type="email"]', timeout=10000)
    await page.fill('input[type="email"]', email)
    await page.press('input[type="email"]', 'Enter')

    # 輸入 Password
    await page.wait_for_selector('input[type="password"]', timeout=10000)
    await page.fill('input[type="password"]', password)
    await page.click('button:has-text("下一步")')

    # 等待首頁載入
    await page.wait_for_url(HOME_URL, timeout=60000)
    if not await is_logged_in(page):
        raise RuntimeError("登入失敗：未偵測到登入狀態。")

    print("✅ 登入成功！")
    return page, True

async def launch_and_login(email: str, password: str) -> Page:
    # 確保 user_data 資料夾存在

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)

    if os.path.exists(STATE_FILE):
        print(f"📥 使用現有 state.json: {STATE_FILE}")
        context = await browser.new_context(storage_state=STATE_FILE)
    else:
        print("📦 未找到 state.json，使用空白 context 並準備匯出新狀態")
        context = await browser.new_context()

    # 關閉預設空白分頁
    for p in list(context.pages):
        if p.url == "about:blank":
            await p.close()

    # 執行登入檢查或流程
    page, did_login = await login_if_needed(context, email, password)

    # 登入成功後，儲存最新狀態
    print(f"📤 匯出 storage state 到 {STATE_FILE}")
    if did_login:
        await context.storage_state(path=STATE_FILE)
    else:
        print("🔄 無需更新 state.json")

    return page

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch Playwright with storageState login.")
    parser.add_argument('-a', '--account', required=True, help='ShopBack login email')
    parser.add_argument('-p', '--password', required=True, help='ShopBack login password')
    args = parser.parse_args()

    page = asyncio.run(launch_and_login(email=args.account, password=args.password))
