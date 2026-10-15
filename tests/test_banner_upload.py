import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'executor'))
import upload_google_drive as uploader


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()
        self.filename = '2026_1014_web_banner_蝦皮_101.png'
        (self.folder / self.filename).write_bytes(b'current image')
        (self.folder / 'banner_1.png').write_bytes(b'old image')
        self.manifest = self.folder / 'manifest.json'
        self.data = {'version': 1, 'complete': True, 'banners': [{
            'filename': self.filename, 'capture_date': '2026_1014',
            'brand': '蝦皮', 'asset_id': '101'}]}
        self.save_manifest()

    def save_manifest(self):
        self.manifest.write_text(json.dumps(self.data), encoding='utf-8')

    def test_upload_receives_current_files_directly_from_banners(self):
        drive = Mock()
        drive.files.return_value.create.return_value.execute.return_value = {'id': 'mock-file-id'}
        count = uploader.upload_folder_to_drive(drive, self.folder, 'mock-folder', self.manifest)
        self.assertEqual(count, 1)
        call = drive.files.return_value.create.call_args
        self.assertEqual(call.kwargs['body'], {'name': self.filename, 'parents': ['mock-folder']})
        media = call.kwargs['media_body']
        self.assertEqual(Path(media._filename), self.folder / self.filename)
        self.assertNotIn('rename_banners', media._filename)
        self.assertEqual(media.mimetype(), 'image/png')
        drive.files.return_value.create.assert_called_once()

    def test_unnamed_banner_is_passed_to_upload_by_asset_id(self):
        filename = '2026_1014_web_banner_101.png'
        (self.folder / filename).write_bytes(b'unnamed current image')
        self.data['banners'][0].update(brand=None, filename=filename, brand_source='asset_id')
        self.save_manifest()
        drive = Mock()
        drive.files.return_value.create.return_value.execute.return_value = {'id': 'mock-file-id'}
        self.assertEqual(uploader.upload_folder_to_drive(drive, self.folder, 'mock-folder', self.manifest), 1)
        call = drive.files.return_value.create.call_args
        self.assertEqual(call.kwargs['body']['name'], filename)
        self.assertEqual(Path(call.kwargs['media_body']._filename), self.folder / filename)

    def test_dry_run_never_authenticates_or_uploads(self):
        args = argparse.Namespace(local_path=self.folder, manifest=self.manifest, dry_run=True,
                                  credentials_json=None, token_base64='must not decode')
        with patch.object(uploader, 'authenticate_oauth_from_json') as auth, \
                patch.object(uploader, 'build') as build, \
                patch.object(uploader, 'upload_files_to_drive') as upload:
            self.assertEqual(uploader.main(args), [self.folder / self.filename])
            auth.assert_not_called()
            build.assert_not_called()
            upload.assert_not_called()

    def test_incomplete_manifest_fails_before_authentication(self):
        self.data['complete'] = False
        self.save_manifest()
        args = argparse.Namespace(local_path=self.folder, manifest=self.manifest, dry_run=False)
        with patch.object(uploader, 'authenticate_oauth_from_json') as auth:
            with self.assertRaises(ValueError):
                uploader.main(args)
            auth.assert_not_called()

    def test_missing_image_and_duplicate_names_fail(self):
        self.data['banners'].append(self.data['banners'][0].copy())
        self.save_manifest()
        with self.assertRaises(ValueError):
            uploader.get_upload_files(self.folder, self.manifest)
        self.data['banners'].pop()
        self.save_manifest()
        (self.folder / self.filename).unlink()
        with self.assertRaises(ValueError):
            uploader.get_upload_files(self.folder, self.manifest)

    def test_filename_must_match_metadata_and_cannot_escape_folder(self):
        self.data['banners'][0]['filename'] = '../other.png'
        self.save_manifest()
        with self.assertRaises(ValueError):
            uploader.get_upload_files(self.folder, self.manifest)
        self.data['banners'][0]['capture_date'] = '../2026_1014'
        self.save_manifest()
        with self.assertRaises(ValueError):
            uploader.get_upload_files(self.folder, self.manifest)

    def test_other_workflows_can_still_upload_generic_folder_or_single_file(self):
        self.assertEqual(len(uploader.get_upload_files(self.folder, '')), 2)
        self.assertEqual(uploader.get_upload_files(self.folder / self.filename),
                         [self.folder / self.filename])

    def test_upload_failure_does_not_report_success(self):
        with patch.object(uploader, 'upload_file_to_drive', return_value=None):
            with self.assertRaises(RuntimeError):
                uploader.upload_folder_to_drive(Mock(), self.folder, 'mock-folder', self.manifest)

    def test_workflow_passes_banners_and_manifest_without_rename_stage(self):
        import yaml
        root = Path(__file__).resolve().parents[1]
        workflow = yaml.safe_load((root / '.github/workflows/screenshot_and_upload.yml').read_text())
        steps = workflow['jobs']['screenshot']['steps']
        upload = next(s for s in steps if s.get('uses') == './.github/actions/uploadToGoogleDrive')
        self.assertEqual(upload['with']['local_folder'], './banners')
        self.assertEqual(upload['with']['manifest_path'], './banners/manifest.json')
        self.assertFalse(any('rename_banner' in s.get('run', '') for s in steps))
        action = yaml.safe_load((root / '.github/actions/uploadToGoogleDrive/action.yml').read_text())
        self.assertIn('--manifest "$UPLOAD_MANIFEST_PATH"', action['runs']['steps'][0]['run'])


if __name__ == '__main__':
    unittest.main()
