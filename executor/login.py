import os
import asyncio
import argparse
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Page, BrowserContext

LOGIN_URL = "https://www.shopback.com.tw/login"
HOME_URL = "https://www.shopback.com.tw"

script_dir = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(script_dir, '..', 'state.json')


async def is_logged_in(page: Page) -> bool:
    return not await page.is_visible("text=登入")


async def dismiss_country_dialog(page: Page) -> None:
    # CI runner 在美國，ShopBack 會彈出「確認國家/地區」dialog 詢問是否切換至美國站
    # 直接點「繼續使用 台灣 網站」關掉它
    try:
        btn = page.locator('button:has-text("繼續使用")')
        await btn.wait_for(state="visible", timeout=3000)
        await btn.click()
        print("🌏 已關閉國家/地區確認 dialog")
    except Exception:
        pass


async def login_if_needed(context: BrowserContext, email: str, password: str) -> tuple[Page, bool]:
    if not email or not password:
        raise ValueError("必須提供 email 及 password，請使用 -a 和 -p 提供")

    page = await context.new_page()
    await page.goto(HOME_URL, wait_until="load", timeout=30000)
    await dismiss_country_dialog(page)

    if await is_logged_in(page):
        print("✅ 已登入，跳過登入流程。")
        return page, False

    print("🔐 未登入，開始登入...")
    await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
    await dismiss_country_dialog(page)

    try:
        await page.wait_for_selector('input[type="email"]', timeout=15000)
        await page.fill('input[type="email"]', email)
        await page.press('input[type="email"]', 'Enter')

        await page.wait_for_selector('input[type="password"]', timeout=20000)
        await page.fill('input[type="password"]', password)
        await page.click('button:has-text("下一步")')
    except Exception as e:
        await page.screenshot(path="debug_login_failure.png", full_page=True)
        raise RuntimeError(f"登入步驟失敗（截圖已存至 debug_login_failure.png）：{e}") from e

    await page.wait_for_url(f"{HOME_URL}**", timeout=60000)
    if not await is_logged_in(page):
        raise RuntimeError("登入失敗：未偵測到登入狀態。")

    print("✅ 登入成功！")
    return page, True


@asynccontextmanager
async def launch_and_login(email: str, password: str):
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    try:
        if os.path.exists(STATE_FILE):
            print(f"📥 使用現有 state.json: {STATE_FILE}")
            context = await browser.new_context(storage_state=STATE_FILE)
        else:
            print("📦 未找到 state.json，使用空白 context 並準備匯出新狀態")
            context = await browser.new_context()

        for p in list(context.pages):
            if p.url == "about:blank":
                await p.close()

        page, did_login = await login_if_needed(context, email, password)

        if did_login:
            print(f"📤 匯出 storage state 到 {STATE_FILE}")
            await context.storage_state(path=STATE_FILE)
        else:
            print("🔄 無需更新 state.json")

        yield page
    finally:
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch Playwright with storageState login.")
    parser.add_argument('-a', '--account', required=True, help='ShopBack login email')
    parser.add_argument('-p', '--password', required=True, help='ShopBack login password')
    args = parser.parse_args()

    async def main():
        async with launch_and_login(email=args.account, password=args.password):
            pass

    asyncio.run(main())
