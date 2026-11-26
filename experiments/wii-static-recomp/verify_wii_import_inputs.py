"""Check import paths and failure handling with synthetic bytes, not a Wii image."""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

import prepare_wii_us_copy as importer
import verify_wii_us_copy as verifier


class ImportInputs(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='openshsm-import-inputs-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'original/DATA'
        files = {'sys/boot.bin': b'R5WEA4\0\0',
            'sys/main.dol': b'synthetic DOL fixture',
            'files/sample': b'synthetic asset fixture'}
        rows = []
        for name, data in files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            rows.append({'path': name, 'bytes': len(data),
                'sha256': hashlib.sha256(data).hexdigest()})
        self.manifest = self.root / 'fixture.json'
        self.manifest.write_text(json.dumps({'gameId': 'R5WEA4',
            'revision': 0, 'files': rows}))
        for target, name, value in (
            (importer, 'MANIFEST', self.manifest),
            (verifier, 'MANIFEST', self.manifest),
            (verifier, 'EXPECTED_DOL_SHA256', verifier.digest(self.source / 'sys/main.dol')),
        ):
            patch = mock.patch.object(target, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.destination = self.root / 'imported'
        self.image = self.root / 'synthetic.iso'
        self.image.write_bytes(b'not a disc image')
        self.tool = Path(sys.executable).resolve(strict=True)

    def link(self, path, target, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'Symlink creation unavailable: {error}')

    def test_copy_and_report(self):
        report = importer.prepare(self.source.parent, self.destination)
        self.assertEqual(report['files'], 3)
        self.assertEqual(report['destination'], str(self.destination / 'DATA'))
        self.assertEqual(verifier.audit_copy(self.destination)['files'], 3)
        self.assertEqual(json.loads((self.destination / 'import.json').read_text()), report)
        self.assertFalse((self.destination / '.DATA.partial').exists())
        self.assertEqual(verifier.audit_copy(self.source)['files'], 3)

    def test_existing_destination_untouched(self):
        self.destination.mkdir()
        marker = self.destination / 'keep'
        marker.write_bytes(b'unchanged')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            importer.prepare(self.source, self.destination)
        self.assertEqual(marker.read_bytes(), b'unchanged')

    def test_direct_child_refused_before_audit(self):
        with mock.patch.object(importer, 'audit_copy') as audit:
            with self.assertRaisesRegex(ValueError, 'outside the original'):
                importer.prepare(self.source, self.source / 'new-import')
            audit.assert_not_called()
        self.assertFalse((self.source / 'new-import').exists())

    def test_destination_parent_alias_into_source_refused(self):
        alias = self.root / 'alias'
        self.link(alias, self.source, directory=True)
        with self.assertRaisesRegex(ValueError, 'outside the original'):
            importer.prepare(self.source, alias / 'new-import')
        self.assertFalse((self.source / 'new-import').exists())

    def test_source_parent_alias_refused(self):
        alias = self.root / 'alias'
        self.link(alias, self.source.parent, directory=True)
        with self.assertRaisesRegex(ValueError, 'outside the original'):
            importer.prepare(alias / 'DATA', self.source / 'new-import')
        self.assertFalse((self.source / 'new-import').exists())

    def test_destination_dotdot_alias_refused(self):
        (self.source / 'subdir').mkdir()
        with self.assertRaisesRegex(ValueError, 'outside the original'):
            importer.prepare(self.source, self.source / 'subdir/../new-import')
        self.assertFalse((self.source / 'new-import').exists())

    def test_dangling_destination_symlink_refused(self):
        target = self.root / 'missing'
        self.link(self.destination, target, directory=True)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            importer.prepare(self.source, self.destination)
        self.assertTrue(self.destination.is_symlink())
        self.assertFalse(target.exists())

    def test_external_parent_alias_canonicalized(self):
        external = self.root / 'external'
        external.mkdir()
        alias = self.root / 'alias'
        self.link(alias, external, directory=True)
        report = importer.prepare(self.source, alias / 'imported')
        self.assertEqual(report['destination'], str(external / 'imported/DATA'))

    def test_changed_source_keeps_partial_without_success(self):
        original = importer.copy_checked

        def changed(source, target, expected):
            if expected['path'] == 'files/sample':
                source.write_bytes(b'changed after audit')
            original(source, target, expected)

        with mock.patch.object(importer, 'copy_checked', side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, 'Source changed during import'):
                importer.prepare(self.source, self.destination)
        self.assertTrue((self.destination / '.DATA.partial').is_dir())
        self.assertFalse((self.destination / 'DATA').exists())
        self.assertFalse((self.destination / 'import.json').exists())

    def test_missing_parent_creates_nothing(self):
        with self.assertRaisesRegex(ValueError, 'parent does not exist'):
            importer.prepare(self.source, self.root / 'missing/imported')
        self.assertFalse((self.root / 'missing').exists())

    def test_low_space_creates_nothing(self):
        with mock.patch.object(importer.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(ValueError, 'Insufficient free space'):
                importer.prepare(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_image_failure_has_no_success_report(self):
        with mock.patch.object(importer.subprocess, 'run', return_value=SimpleNamespace(returncode=9)):
            with self.assertRaisesRegex(RuntimeError, 'DolphinTool exited 9'):
                importer.prepare_image(self.image, self.tool, self.destination)
        self.assertTrue((self.destination / 'extract.log').is_file())
        self.assertFalse((self.destination / 'import.json').exists())

    def test_image_empty_extraction_refused(self):
        with mock.patch.object(importer.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            with self.assertRaisesRegex(RuntimeError, 'Image import incomplete'):
                importer.prepare_image(self.image, self.tool, self.destination)
        self.assertEqual(run.call_args.args[0], [str(self.tool), 'extract',
            '--input', str(self.image), '--output', str(self.destination),
            '--gameonly', '--quiet'])
        self.assertFalse((self.destination / 'import.json').exists())

    def test_image_timeout_has_no_success_report(self):
        with mock.patch.object(importer.subprocess, 'run',
                side_effect=subprocess.TimeoutExpired('synthetic extractor', 3600)):
            with self.assertRaisesRegex(RuntimeError, 'Image import incomplete'):
                importer.prepare_image(self.image, self.tool, self.destination)
        self.assertFalse((self.destination / 'import.json').exists())

    def test_missing_image_creates_nothing(self):
        with self.assertRaisesRegex(ValueError, 'Image must be'):
            importer.prepare_image(self.root / 'missing.iso', self.tool, self.destination)
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()
