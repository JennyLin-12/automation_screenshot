"""Validate the current capture manifest before selecting files for upload."""
import json
from pathlib import Path

from banner_capture import banner_filename


def manifest_files(banners_dir, manifest_path):
    banners_dir = Path(banners_dir).resolve()
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    if manifest.get('version') != 1 or manifest.get('complete') is not True or not manifest.get('banners'):
        raise ValueError('Banner manifest 不完整，停止上傳，避免缺漏或舊圖片')
    sources = []
    names = set()
    for entry in manifest['banners']:
        filename = entry['filename']
        if filename != banner_filename(entry['brand'], entry['asset_id'], entry['capture_date']):
            raise ValueError('Banner manifest 的檔名與品牌／素材 ID 不符')
        source = (banners_dir / filename).resolve()
        if source.parent != banners_dir or filename in names or not source.is_file():
            raise ValueError(f'Banner 圖片缺漏、路徑錯誤或重複：{filename}')
        names.add(filename)
        sources.append(source)
    return sources
