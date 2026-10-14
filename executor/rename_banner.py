"""Copy only this run's validated, DOM-named screenshots to the upload folder."""
import argparse
import shutil
from pathlib import Path

from banner_manifest import manifest_files

ROOT = Path(__file__).resolve().parent.parent


def rename_banners(banners_dir=ROOT / 'banners', output_dir=ROOT / 'rename_banners'):
    banners_dir, output_dir = Path(banners_dir), Path(output_dir)
    sources = manifest_files(banners_dir, banners_dir / 'manifest.json')
    names = {source.name for source in sources}
    output_dir.mkdir(parents=True, exist_ok=True)
    # Reject stale output rather than deleting pre-existing user files.
    stale = {p.name for p in output_dir.iterdir() if p.is_file()} - names
    if stale:
        raise ValueError('輸出資料夾包含舊檔案，請使用乾淨的 rename_banners 資料夾')
    for source in sources:
        shutil.copy2(source, output_dir / source.name)
        print(f'[Rename] {source.name}')
    return [source.name for source in sources]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prepare DOM-named banners for upload')
    parser.add_argument('--banners-dir', type=Path, default=ROOT / 'banners')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'rename_banners')
    args = parser.parse_args()
    rename_banners(args.banners_dir, args.output_dir)
