"""Capture stable hero banners and keep their DOM identity with each image."""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERO_SELECTOR = '[data-ui-element-name="hero banner"]'
MAX_SLIDES = 50
SNAPSHOT_JS = r"""
() => {
  const first = document.querySelector('[data-ui-element-name="hero banner"]');
  if (!first) return null;
  const track = first.closest('.carousel-container');
  const layout = track && track.closest('.carousel-layout');
  if (!layout) return null;
  const box = layout.getBoundingClientRect();
  const center = (box.left + box.right) / 2;
  const items = Array.from(track.querySelectorAll('[data-ui-element-name="hero banner"]'));
  const records = items.map((el, index) => {
    const r = el.getBoundingClientRect();
    const images = Array.from(el.querySelectorAll('img'));
    const cs = getComputedStyle(el);
    const overlap = Math.max(0, Math.min(r.right, box.right) - Math.max(r.left, box.left));
    return {
      dom_index: index,
      position: el.getAttribute('data-feature-position'),
      brand: el.getAttribute('data-merchant-name'),
      asset_id: el.getAttribute('data-asset-id'),
      asset_name: el.getAttribute('data-asset-name'),
      image_alt: images.map(img => img.getAttribute('alt')).find(alt => alt && alt.trim()) || null,
      rect: [r.x, r.y, r.width, r.height, box.x, box.y, box.width, box.height],
      distance: Math.abs((r.left + r.right) / 2 - center),
      visible: overlap > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none',
      loaded: images.length > 0 && images.every(img => img.complete && img.naturalWidth > 0)
    };
  });
  const visible = records.filter(r => r.visible).sort((a, b) => a.distance - b.distance);
  return {items: records, active: visible[0] || null};
}
"""


def banner_filename(brand, asset_id, date_str):
    if not isinstance(date_str, str) or not re.fullmatch(r'[0-9]{4}_[0-9]{4}', date_str):
        raise ValueError('Banner 日期格式必須是 YYYY_MMDD')
    if not isinstance(asset_id, str) or not re.fullmatch(r'[0-9]+', asset_id):
        raise ValueError('Banner 缺少有效 data-asset-id')
    # Keep Chinese, spaces and punctuation, replacing characters unsafe in filenames.
    brand = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', '_', brand or '').strip().rstrip('. ')
    label = f'{brand}_{asset_id}' if brand else asset_id
    return f'{date_str}_web_banner_{label}.png'


def resolve_banner(record):
    """Use explicit DOM metadata; an unnamed banner still has a stable asset ID."""
    result = dict(record)
    candidates = (('brand', 'data-merchant-name'), ('asset_name', 'data-asset-name'),
                  ('image_alt', 'img.alt'))
    result['brand'] = None
    result['brand_source'] = 'asset_id'
    result.setdefault('image_alt', None)
    for key, source in candidates:
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        if key != 'brand':
            value = re.sub(r'_\d{4}-\d{2}-\d{2}_web_homepage_hero_banner$', '', value,
                           flags=re.IGNORECASE).strip()
        if not value.rstrip('. '):
            continue
        result['brand'] = value
        result['brand_source'] = source
        break
    return result


async def read_snapshot(page):
    snapshot = await page.evaluate(SNAPSHOT_JS)
    if not snapshot:
        return None
    return {'items': [resolve_banner(record) for record in snapshot['items']],
            'active': resolve_banner(snapshot['active']) if snapshot['active'] else None}


def same_frame(before, after, epsilon=0.5):
    return bool(before and after and after['loaded']
                and before['asset_id'] == after['asset_id']
                and before['brand'] == after['brand']
                and before['position'] == after['position']
                and len(before['rect']) == len(after['rect'])
                and all(abs(a - b) <= epsilon for a, b in zip(before['rect'], after['rect'])))


def write_manifest(output_dir, entries, complete):
    target = output_dir / 'manifest.json'
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'version': 1, 'complete': complete, 'banners': entries},
                                    ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)


async def capture_banners(page, output_dir, *, y_offset=0, timeout_seconds=180,
                          stable_samples=3, poll_seconds=0.1, date_str=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = date_str or datetime.now(ZoneInfo('Asia/Taipei')).strftime('%Y_%m%d')
    entries = []
    write_manifest(output_dir, entries, False)
    first = await read_snapshot(page)
    if not first or not first['items']:
        raise RuntimeError('找不到 hero banner 輪播')
    expected = set()
    for item in first['items']:
        banner_filename(item['brand'], item['asset_id'], date_str)
        expected.add(item['asset_id'])
        if item['brand_source'] != 'data-merchant-name':
            detail = (f"使用 {item['brand_source']}：{item['brand']}" if item['brand']
                      else '無可用名稱，僅使用素材 ID 命名')
            print(f"[WARN] Banner asset_id={item['asset_id']} position={item['position']} "
                  f"缺少 data-merchant-name；{detail}")
    if len(expected) > MAX_SLIDES:
        raise RuntimeError(f'Banner 數量超過安全上限 {MAX_SLIDES}')
    captured = set()

    async def collect():
        previous = None
        stable = 0
        while captured != expected:
            snapshot = await read_snapshot(page)
            if not snapshot or {item['asset_id'] for item in snapshot['items']} != expected:
                raise RuntimeError('截圖期間 banner 清單已變動，請重新執行')
            active = snapshot['active']
            if active and active['loaded'] and same_frame(previous, active):
                stable += 1
            else:
                stable = 1 if active and active['loaded'] else 0
            previous = active
            if stable >= stable_samples and active['asset_id'] not in captured:
                filename = banner_filename(active['brand'], active['asset_id'], date_str)
                viewport = page.viewport_size
                png = await page.screenshot(clip={
                    'x': 0, 'y': y_offset, 'width': viewport['width'],
                    'height': viewport['height'] - y_offset,
                })
                after = await read_snapshot(page)
                # The carousel may advance while Playwright takes the screenshot.
                if after and same_frame(active, after['active']):
                    (output_dir / filename).write_bytes(png)
                    entries.append({key: active[key] for key in
                                    ('asset_id', 'brand', 'brand_source', 'position', 'dom_index', 'asset_name', 'image_alt')}
                                   | {'filename': filename, 'capture_date': date_str, 'captured_at': datetime.now(
                                       ZoneInfo('Asia/Taipei')).isoformat()})
                    captured.add(active['asset_id'])
                    write_manifest(output_dir, entries, False)
                    print(f"[Screenshot] {len(captured)}/{len(expected)} → {filename}")
                else:
                    previous = None
                    stable = 0
            await asyncio.sleep(poll_seconds)

    try:
        await asyncio.wait_for(collect(), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        missing = ', '.join(sorted(expected - captured))
        raise RuntimeError(f'Banner 截圖逾時；尚未截到素材 ID：{missing}') from exc
    write_manifest(output_dir, entries, True)
    return entries
