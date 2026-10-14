import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'executor'))
import login
import banner_screenshot


class HeadlessTests(unittest.IsolatedAsyncioTestCase):
    async def check_login(self, did_login):
        page = Mock(url='https://www.shopback.com.tw')
        context = Mock(pages=[])
        context.storage_state = AsyncMock(return_value={'cookies': [], 'origins': []})
        browser = Mock()
        browser.new_context = AsyncMock(return_value=context)
        browser.close = AsyncMock()
        playwright = Mock()
        playwright.chromium.launch = AsyncMock(return_value=browser)
        playwright.stop = AsyncMock()
        manager = Mock()
        manager.start = AsyncMock(return_value=playwright)
        with patch.object(login, 'async_playwright', return_value=manager), \
                patch.object(login, 'login_if_needed', new=AsyncMock(return_value=(page, did_login))), \
                patch.object(login.os.path, 'exists', return_value=not did_login):
            async with login.launch_and_login('mock-account', 'mock-password') as actual:
                self.assertIs(actual, page)
        browser.close.assert_awaited_once()
        playwright.stop.assert_awaited_once()
        playwright.chromium.launch.assert_awaited_once_with(headless=True)
        if did_login:
            context.storage_state.assert_awaited_once_with(path=login.STATE_FILE)
        else:
            context.storage_state.assert_not_awaited()

    async def test_cached_login_launches_without_window(self):
        await self.check_login(False)

    async def test_new_login_can_save_state_without_undefined_variable(self):
        await self.check_login(True)

    async def test_banner_entrypoint_uses_context_manager_and_closes_on_capture_failure(self):
        for fails in (False, True):
            page = Mock()
            for name in ('set_viewport_size', 'goto', 'wait_for_load_state', 'wait_for_selector'):
                setattr(page, name, AsyncMock())
            page.is_visible = AsyncMock(return_value=False)
            exited = []

            @asynccontextmanager
            async def session(**kwargs):
                try:
                    yield page
                finally:
                    exited.append(True)

            capture = AsyncMock(side_effect=RuntimeError('mock capture failure') if fails else None)
            with patch.object(banner_screenshot, 'launch_and_login', session), \
                    patch.object(banner_screenshot, 'capture_banners', capture), \
                    patch.object(banner_screenshot.os, 'makedirs'):
                if fails:
                    with self.assertRaises(RuntimeError):
                        await banner_screenshot.take_screenshots('mock-account', 'mock-password')
                else:
                    await banner_screenshot.take_screenshots('mock-account', 'mock-password')
            capture.assert_awaited_once_with(page, banner_screenshot.OUTPUT_DIR, y_offset=0)
            self.assertEqual(exited, [True])

    def test_ci_installs_chromium_and_system_dependencies_even_with_cache(self):
        import yaml
        root = Path(__file__).resolve().parents[1]
        action = yaml.safe_load((root / '.github/actions/python-setup/action.yml').read_text())
        steps = action['runs']['steps']
        install = next(s for s in steps if s['name'] == 'Install Playwright browsers')
        self.assertEqual(install['run'], 'playwright install --with-deps chromium')
        self.assertNotIn('if', install)
        cache = next(s for s in steps if s['name'] == 'Cache Playwright browsers')
        self.assertIn("hashFiles('requirements.txt')", cache['with']['key'])


if __name__ == '__main__':
    unittest.main()
