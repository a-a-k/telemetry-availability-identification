import importlib.util
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('v3_main_archive', SCRIPTS / 'archive_v3_main_evidence_v1.py')
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


def source_zip(content):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as target:
        target.writestr('artificial.json', content)
    return buffer.getvalue()


def metadata(identity, name, raw):
    return dict(id=identity, name=name, size_in_bytes=len(raw), expired=False,
                digest='sha256:' + sha256(raw).hexdigest(),
                workflow_run=dict(id=archive.RUN, head_sha=archive.HEAD))


class MainArchiveControls(unittest.TestCase):
    def test_frozen_census_has_all_roles_and_only_main(self):
        names = archive.expected_artifacts()
        self.assertEqual(len(names), 2652)
        self.assertEqual(sum(name.startswith('v3-comparison-raw-') for name in names), 240)
        self.assertEqual(sum(name.startswith('v3-comparison-closed-evaluator-') for name in names), 240)
        self.assertTrue(all(name.endswith('-' + str(archive.RUN)) for name in names))

    def test_missing_cases_remain_explicit_and_foreign_or_changed_bytes_rejected(self):
        row = metadata(1, 'artificial-a', source_zip(b'{}'))
        self.assertEqual(archive.checked_census([row], [row], {'artificial-a', 'absent-b'}), ['absent-b'])
        with self.assertRaisesRegex(ValueError, 'census differ'):
            archive.checked_census([row], [dict(row, digest='sha256:' + '0' * 64)], {'artificial-a'})
        with self.assertRaisesRegex(ValueError, 'source run differs'):
            archive.checked_census([row], [dict(row, workflow_run=dict(id=1, head_sha=archive.HEAD))], {'artificial-a'})
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            archive.checked_census([row], [row, row], {'artificial-a'})

    def test_archive_preserves_source_zip_and_detects_wrong_member_digest(self):
        raw = source_zip(b'{"synthetic":true}')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.zip'
            source.write_bytes(raw)
            bundle = Path(directory) / 'part.zip'
            with zipfile.ZipFile(bundle, 'x') as target:
                archive.add_source(target, source, 'source/1-artificial.zip')
            entry = dict(member='source/1-artificial.zip', sha256=sha256(raw).hexdigest())
            archive.verify_part(bundle, [entry])
            with zipfile.ZipFile(bundle) as result:
                self.assertEqual(result.read(entry['member']), raw)
            with self.assertRaisesRegex(ValueError, 'bytes changed'):
                archive.verify_part(bundle, [dict(entry, sha256='0' * 64)])

    def test_local_execution_cannot_open_payloads_or_call_network(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(archive.transport, 'read_api') as read:
            with self.assertRaisesRegex(ValueError, 'remote only'):
                archive.main()
            read.assert_not_called()

    def test_existing_asset_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'artificial.zip'
            path.write_bytes(source_zip(b'{}'))
            current = dict(id=88, draft=True, published_at=None, tag_name=archive.TAG,
                           target_commitish='a' * 40, assets=[dict(name=path.name, digest='sha256:' + '0' * 64)])
            with patch.object(archive.transport, 'read_api', return_value=current), \
                 patch.object(archive.subprocess, 'run') as command:
                with self.assertRaisesRegex(ValueError, 'never overwritten'):
                    archive.upload(path, current, 'a' * 40)
                command.assert_not_called()

    def test_terminal_two_part_archive_roundtrip_with_mocked_remote(self):
        payloads = {1: source_zip(b'one'), 2: source_zip(b'two')}
        rows = [metadata(i, f'artificial-{i}', raw) for i, raw in payloads.items()]
        run = dict(id=archive.RUN, head_sha=archive.HEAD, path=archive.transport.WORKFLOW,
                   head_repository=dict(full_name=archive.REPO), event='workflow_dispatch',
                   run_attempt=1, status='completed', conclusion='success')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / 'retained'
            source.mkdir()
            (source / 'collection-summary.json').write_text(json.dumps(dict(run_id=archive.RUN, head=archive.HEAD)))
            (source / 'all-artifact-metadata.json').write_text(json.dumps(rows))
            dispatch = base / 'dispatch.json'
            dispatch.write_text(json.dumps(dict(run_id=archive.RUN, head=archive.HEAD,
                                                protocol_sha256=archive.transport.DESIGN_SHA)))
            saved = {}

            def upload(path, release, head):
                saved[path.name] = path.read_bytes()
                return dict(id=len(saved), name=path.name, size=path.stat().st_size,
                            digest='sha256:' + sha256(saved[path.name]).hexdigest(), state='uploaded')

            with patch.multiple(archive, SOURCE=source, OUT=base / 'out', DISPATCH=dispatch,
                                MAX_PART_BYTES=max(map(len, payloads.values())) + 10), \
                 patch.dict(os.environ, dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=archive.REPO,
                                             GITHUB_RUN_ATTEMPT='1', GITHUB_RUN_ID='999')), \
                 patch.object(archive.subprocess, 'check_output', return_value='a' * 40), \
                 patch.object(archive.transport, 'read_api', return_value=run), \
                 patch.object(archive.transport, 'collect_pages', return_value=rows), \
                 patch.object(archive.transport, 'api', side_effect=lambda path: payloads[int(path.split('/')[-2])]), \
                 patch.object(archive, 'expected_artifacts', return_value={row['name'] for row in rows}), \
                 patch.object(archive, 'create_draft', return_value=dict(id=88)), \
                 patch.object(archive, 'upload', side_effect=upload):
                run['status'] = 'in_progress'
                with self.assertRaisesRegex(ValueError, 'terminal original run'):
                    archive.main()
                archive.transport.api.assert_not_called()
                archive.create_draft.assert_not_called()
                run['status'] = 'completed'
                archive.main()
            receipt = json.loads((base / 'out/compact.json').read_bytes())
            self.assertTrue(receipt['qualified'])
            self.assertTrue(receipt['draft'])
            self.assertEqual(receipt['archived_artifacts'], 2)
            self.assertEqual(len(receipt['parts']), 2)
            self.assertFalse(list((base / 'out').glob('*.zip')))
            manifest = json.loads(saved['manifest.json'])
            for part in manifest['parts']:
                with zipfile.ZipFile(io.BytesIO(saved[part['asset']['name']])) as bundle:
                    for item in part['sources']:
                        self.assertEqual(bundle.read(item['member']), payloads[item['artifact_id']])


if __name__ == '__main__':
    unittest.main()
