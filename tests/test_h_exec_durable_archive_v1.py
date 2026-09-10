import importlib.util
import os
from pathlib import Path
from hashlib import sha256
import tempfile
import unittest
from unittest.mock import patch
import zipfile

PATH = Path(__file__).resolve().parents[1]/'scripts/archive_h_exec_evidence_v1.py'
SPEC = importlib.util.spec_from_file_location('h_exec_archive', PATH)
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


class DurableArchiveControls(unittest.TestCase):
    def test_exact_bytes_verified_and_changed_digest_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'artificial.zip'
            with zipfile.ZipFile(path, 'w') as target:
                target.writestr('artificial/values.json', b'{"synthetic":true}\n')
            before = path.read_bytes()
            expected = dict(size_in_bytes=len(before), digest='sha256:'+sha256(before).hexdigest())
            self.assertTrue(archive.verify_zip(path, expected)['zip_crc_verified'])
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaisesRegex(ValueError, 'digest'):
                archive.verify_zip(path, dict(expected, digest='sha256:'+'0'*64))

    def test_unsafe_member_rejected_even_with_matching_provider_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'artificial.zip'
            with zipfile.ZipFile(path, 'w') as target:
                target.writestr('../escape', b'artificial')
            raw = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                archive.verify_zip(path, dict(size_in_bytes=len(raw), digest='sha256:'+sha256(raw).hexdigest()))

    def test_published_release_and_local_payload_execution_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unpublished'):
            archive.checked_draft(dict(draft=False, published_at='2026-01-01'), 'tag', 'a'*40)
        with patch.dict(os.environ, {}, clear=True), patch.object(archive, 'api') as api:
            with self.assertRaisesRegex(ValueError, 'remote only'):
                archive.main()
            api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
