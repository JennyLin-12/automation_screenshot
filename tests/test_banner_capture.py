import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'executor'))
from banner_capture import SNAPSHOT_JS, banner_filename, capture_banners
from rename_banner import rename_banners


def item(asset_id='101', brand='蝦皮', position='1', index=0, x=0, loaded=True):
    return dict(asset_id=asset_id, brand=brand, position=position, dom_index=index,
                asset_name=brand, rect=[x, 100, 100, 50, 0, 100, 100, 50], loaded=loaded)


class FakePage:
    viewport_size = {'width': 1280, 'height': 800}

    def __init__(self, items, sequence, switch_on_shot=None):
        self.items = items
        self.sequence = iter(sequence)
        self.active = items[0]
        self.switch_on_shot = switch_on_shot
        self.shots = []

    async def evaluate(self, script):
        self.active = next(self.sequence, self.active)
        return {'items': self.items, 'active': self.active}

    async def screenshot(self, **kwargs):
        shot_id = self.active['asset_id']
        self.shots.append(shot_id)
        if self.switch_on_shot:
            self.sequence = iter(self.switch_on_shot)
            self.switch_on_shot = None
        return shot_id.encode()


class CaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_and_same_brand_different_ids(self):
        a, b = item(), item('102', position='2', index=1)
        page = FakePage([a, b], [a] * 5 + [b] * 5)
        with tempfile.TemporaryDirectory() as tmp:
            entries = await capture_banners(page, tmp, date_str='2026_1014', poll_seconds=0,
                                            timeout_seconds=1)
            self.assertEqual({e['filename'] for e in entries}, {
                '2026_1014_web_banner_蝦皮_101.png', '2026_1014_web_banner_蝦皮_102.png'})
            target = Path(tmp) / 'upload'
            (Path(tmp) / 'old.png').write_bytes(b'old')
            rename_banners(tmp, target)
            self.assertEqual({p.name for p in target.iterdir()}, {e['filename'] for e in entries})
            self.assertTrue(json.loads((Path(tmp) / 'manifest.json').read_text())['complete'])
            # A single static banner must finish without a switch event.
            single = Path(tmp) / 'single'
            await capture_banners(FakePage([a], [a]), single, poll_seconds=0, timeout_seconds=1)
            self.assertEqual(len(list(single.glob('*.png'))), 1)

    async def test_switch_during_screenshot_discards_mismatched_image(self):
        a, b = item(), item('102', brand='Klook', position='2', index=1)
        page = FakePage([a, b], [a] * 4, switch_on_shot=[b] * 5 + [a] * 5)
        with tempfile.TemporaryDirectory() as tmp:
            entries = await capture_banners(page, tmp, poll_seconds=0, timeout_seconds=1)
            self.assertEqual(page.shots, ['101', '102', '101'])
            for entry in entries:
                self.assertEqual((Path(tmp) / entry['filename']).read_bytes(), entry['asset_id'].encode())

    async def test_waits_for_loaded_and_stable_image(self):
        a = item()
        page = FakePage([a], [a, item(loaded=False), item(x=30), item(x=10)] + [a] * 5)
        with tempfile.TemporaryDirectory() as tmp:
            await capture_banners(page, tmp, poll_seconds=0, timeout_seconds=1)
            self.assertEqual(page.shots, ['101'])

    async def test_timeout_is_failure_and_partial_manifest_cannot_upload(self):
        a, b = item(), item('102', position='2')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, '102'):
                await capture_banners(FakePage([a, b], [a]), tmp, poll_seconds=0.001,
                                      timeout_seconds=0.02)
            self.assertFalse(json.loads((Path(tmp) / 'manifest.json').read_text())['complete'])
            with self.assertRaises(ValueError):
                rename_banners(tmp, Path(tmp) / 'upload')

    async def test_missing_brand_fails_instead_of_guessing(self):
        a = item(brand=None)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                await capture_banners(FakePage([a], [a]), tmp)

    def test_filename_sanitizes_paths_and_preserves_brand(self):
        self.assertEqual(banner_filename('IHG Hotels & Resorts 洲際酒店集團', '123', '2026_1014'),
                         '2026_1014_web_banner_IHG Hotels & Resorts 洲際酒店集團_123.png')
        self.assertEqual(banner_filename('../A/B:品牌', '123', '2026_1014'),
                         '2026_1014_web_banner_.._A_B_品牌_123.png')
        with self.assertRaises(ValueError):
            banner_filename('Brand', '../123', '2026_1014')

    async def test_stale_output_is_preserved_and_rejected(self):
        a = item()
        with tempfile.TemporaryDirectory() as tmp:
            await capture_banners(FakePage([a], [a]), tmp, poll_seconds=0, timeout_seconds=1)
            target = Path(tmp) / 'upload'
            target.mkdir()
            (target / 'old.png').write_bytes(b'old')
            with self.assertRaises(ValueError):
                rename_banners(tmp, target)
            self.assertEqual((target / 'old.png').read_bytes(), b'old')


class BrowserGeometryTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_dom_handles_desktop_neighbors_and_wrap_transform(self):
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page(viewport={'width': 1280, 'height': 800})
                await page.set_content('''<style>
                  .carousel-layout {width:1000px;overflow:hidden;margin-left:100px}
                  .carousel-container {display:flex;transform:translateX(-1800px)}
                  .slide {flex:0 0 800px;height:100px}
                </style><div class="carousel-layout"><div class="carousel-container">
                  <div class="slide" data-ui-element-name="hero banner" data-merchant-name="蝦皮"
                    data-asset-id="101" data-feature-position="1" style="transform:translateX(2400px)">
                    <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/%3E"></div>
                  <div class="slide" data-ui-element-name="hero banner" data-merchant-name="Klook"
                    data-asset-id="102" data-feature-position="2"></div>
                  <div class="slide" data-ui-element-name="hero banner" data-merchant-name="Agoda"
                    data-asset-id="103" data-feature-position="3"></div>
                </div></div>''')
                snapshot = await page.evaluate(SNAPSHOT_JS)
                self.assertEqual(snapshot['active']['asset_id'], '103')
                # At the looping boundary, the first DOM node moves to the end.
                await page.locator('.carousel-container').evaluate(
                    "el => el.style.transform = 'translateX(-2300px)'")
                snapshot = await page.evaluate(SNAPSHOT_JS)
                self.assertEqual(snapshot['active']['asset_id'], '101')
                self.assertEqual(snapshot['active']['dom_index'], 0)
                self.assertEqual(snapshot['active']['position'], '1')
            finally:
                await browser.close()

    async def test_browser_capture_and_prepare_produce_matching_images(self):
        from PIL import Image
        from playwright.async_api import async_playwright
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page(viewport={'width': 1280, 'height': 800})
                await page.set_content("""<style>body{margin:0}.carousel-layout{width:1280px;overflow:hidden}
                  .carousel-container{display:flex}.slide{flex:0 0 1280px;height:800px}
                  </style><div class="carousel-layout"><div class="carousel-container">
                  <div class="slide" style="background:red" data-ui-element-name="hero banner"
                    data-merchant-name="蝦皮" data-asset-id="101" data-feature-position="1">
                    <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/%3E"></div>
                  <div class="slide" style="background:lime" data-ui-element-name="hero banner"
                    data-merchant-name="蝦皮" data-asset-id="102" data-feature-position="2">
                    <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/%3E"></div>
                  </div></div><script>let i=0;setInterval(()=>{
                    i=1-i;document.querySelector('.carousel-container').style.transform=`translateX(${-1280*i}px)`;
                  },600)</script>""")
                with tempfile.TemporaryDirectory() as tmp:
                    entries = await capture_banners(page, tmp, timeout_seconds=5, poll_seconds=0.02)
                    target = Path(tmp) / 'upload'
                    rename_banners(tmp, target)
                    self.assertEqual(len(entries), 2)
                    expected = {'101': (255, 0, 0), '102': (0, 255, 0)}
                    for entry in entries:
                        with Image.open(target / entry['filename']) as img:
                            self.assertEqual(img.getpixel((500, 400))[:3], expected[entry['asset_id']])
            finally:
                await browser.close()


if __name__ == '__main__':
    unittest.main()
