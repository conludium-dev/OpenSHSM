"""Synthetic first-run import checks; no Tk, disc decoder or game process."""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import json
import shutil
import unittest

import launcher_import as launcher
import launch_stock_owner_macos as macos
import launch_stock_owner_windows as windows
from verify_wii_import_inputs import ImportInputs
import prepare_wii_us_copy as importer


class LauncherImport(ImportInputs):
    def setUp(self):
        super().setUp()
        self.user = self.root / 'user'

    def test_managed_copy_and_reuse(self):
        game = launcher.import_game(self.source, self.user, extracted=True)
        self.assertEqual(game, self.user / 'wii-import/DATA')
        report = json.loads((game.parent / 'import.json').read_text())
        self.assertEqual(report['destination'], str(game))
        with mock.patch.object(launcher, 'show_import', side_effect=AssertionError('Opened Tk')):
            self.assertEqual(launcher.resolve_game_data(None, self.user), game)
        self.assertFalse(list(self.user.glob('wii-import.partial-*')))

    def test_image_uses_actual_importer_and_verifier(self):
        def extract(arguments, **kwargs):
            self.assertEqual(arguments[:2], [str(self.tool), 'extract'])
            self.assertEqual(arguments[-2:], ['--gameonly', '--quiet'])
            destination = Path(arguments[arguments.index('--output') + 1])
            shutil.copytree(self.source, destination / 'DATA')
            return SimpleNamespace(returncode=0)
        with mock.patch.object(importer.subprocess, 'run', side_effect=extract):
            game = launcher.resolve_game_data(None, self.user,
                interactive=False, image=self.image, dolphin_tool=self.tool)
        self.assertEqual(game, self.user / 'wii-import/DATA')

    def test_failure_preserved_retry_succeeds(self):
        with mock.patch.object(importer.subprocess, 'run', return_value=SimpleNamespace(returncode=9)):
            with self.assertRaisesRegex(RuntimeError, 'DolphinTool exited 9'):
                launcher.import_game(self.image, self.user, self.tool)
        partials = list(self.user.glob('wii-import.partial-*'))
        self.assertEqual(len(partials), 1)
        self.assertTrue((partials[0] / 'extract.log').is_file())
        self.assertFalse((self.user / 'wii-import').exists())
        launcher.import_game(self.source, self.user, extracted=True)
        self.assertTrue(partials[0].is_dir())

    def test_tampered_import_refused_without_wizard(self):
        game = launcher.import_game(self.source, self.user, extracted=True)
        (game / 'files/sample').write_bytes(b'bad')
        with mock.patch.object(launcher, 'show_import', side_effect=AssertionError('Opened Tk')):
            with self.assertRaises(ValueError):
                launcher.resolve_game_data(None, self.user)

    def test_cancel_and_noninteractive_no_mutation(self):
        with mock.patch.object(launcher, 'show_import', return_value=None):
            self.assertIsNone(launcher.resolve_game_data(None, self.user))
        with self.assertRaisesRegex(ValueError, 'Нет Wii DATA'):
            launcher.resolve_game_data(None, self.user, interactive=False)
        self.assertFalse(self.user.exists())

    def test_existing_target_and_user_link_refused(self):
        launcher.import_game(self.source, self.user, extracted=True)
        before = (self.user / 'wii-import/import.json').read_bytes()
        with self.assertRaises(ValueError):
            launcher.import_game(self.source, self.user, extracted=True)
        self.assertEqual((self.user / 'wii-import/import.json').read_bytes(), before)
        alias = self.root / 'user-alias'
        self.link(alias, self.user, directory=True)
        with self.assertRaisesRegex(ValueError, 'ссылкой'):
            launcher.import_game(self.source, alias, extracted=True)

    def test_both_owner_launchers_cancel_before_validation_or_process(self):
        for owner in (macos, windows):
            with mock.patch.object(launcher, 'show_import', return_value=None), \
                    mock.patch.object(owner, 'validate', side_effect=AssertionError('Validated build')), \
                    mock.patch.object(owner.subprocess, 'Popen', side_effect=AssertionError('Started game')):
                self.assertIn('CANCELLED', owner.launch(self.root, None, self.user)['result'])

    def test_check_only_and_no_settings_never_import(self):
        for owner in (macos, windows):
            with mock.patch.object(launcher, 'show_import', side_effect=AssertionError('Opened Tk')):
                for options in ({'check_only': True}, {'show_launcher': False}):
                    with self.assertRaisesRegex(ValueError, 'Нет Wii DATA'):
                        owner.launch(self.root, None, self.user, **options)
                with self.assertRaisesRegex(ValueError, '--import-image'):
                    owner.launch(self.root, None, self.user, check_only=True, image=self.image)
        self.assertFalse(self.user.exists())


if __name__ == '__main__':
    unittest.main()
