from hashlib import sha256
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('main_archive_retainer', SCRIPTS / 'retain_v3_main_archive_compact_v1.py')
retainer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(retainer)


class CompactArchiveBoundaryControls(unittest.TestCase):
    def test_only_provenance_members_are_accepted(self):
        def bundle(extra=False):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as archive:
                for name in retainer.MEMBERS:
                    archive.writestr(name, b'{}\n')
                if extra:
                    archive.writestr('artificial-native.json', b'not allowed locally')
            data = stream.getvalue()
            return data, dict(expired=False, size_in_bytes=len(data), digest='sha256:' + sha256(data).hexdigest())
        data, item = bundle()
        self.assertEqual(set(retainer.unpack(data, item)), retainer.MEMBERS)
        with self.assertRaisesRegex(ValueError, 'ZIP bytes'):
            retainer.unpack(data, dict(item, digest='sha256:' + '0' * 64))
        data, item = bundle(extra=True)
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            retainer.unpack(data, item)

    def test_resource_text_hash_and_absence_are_preserved_without_extra_payload(self):
        raw = b'User time (seconds): 1.25\n'
        record = dict(artifact_id=1, artifact_name='artificial', member='process-resource-usage.txt',
                      present=True, bytes=len(raw), sha256=sha256(raw).hexdigest(), text=raw.decode(),
                      scope='complete timed PMX extraction command and accounted children')
        self.assertEqual(retainer.resource_bytes(record), raw)
        with self.assertRaisesRegex(ValueError, 'resource bytes'):
            retainer.resource_bytes(dict(record, text='changed'))
        with self.assertRaisesRegex(ValueError, 'unlisted'):
            retainer.resource_bytes(dict(record, native_payload='not allowed'))
        missing = {key:record[key] for key in ('artifact_id', 'artifact_name', 'member')}
        missing.update(present=False, reason='resource_record_not_in_source_artifact')
        self.assertIsNone(retainer.resource_bytes(missing))

    def test_running_failed_or_repeated_archive_cannot_download_any_payload(self):
        base = dict(id=123, path=retainer.WORKFLOW, run_attempt=1, status='completed', conclusion='success',
                    head_repository=dict(full_name=retainer.transport.REPO), event='workflow_run')
        for changes in (dict(status='in_progress'), dict(conclusion='failure'), dict(run_attempt=2)):
            with self.subTest(changes=changes), \
                 patch.object(retainer.transport, 'read_api', return_value=dict(base, **changes)), \
                 patch.object(retainer.transport, 'collect_pages') as metadata, \
                 patch.object(retainer.transport, 'api') as payload:
                with self.assertRaisesRegex(ValueError, 'terminal state'):
                    retainer.retain(123)
                metadata.assert_not_called()
                payload.assert_not_called()


if __name__ == '__main__':
    unittest.main()
