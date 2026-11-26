"""Verify deterministic Russian and English desktop UI selection."""
import unittest

from launcher_locale import language, runtime_environment, text


class LauncherLocale(unittest.TestCase):
    def test_explicit_override(self):
        self.assertEqual(language({'OPENSHSM_LANGUAGE': 'ru-RU'}, 'en_US'), 'ru')
        self.assertEqual(language({'OPENSHSM_LANGUAGE': 'en_US'}, 'ru_RU'), 'en')

    def test_system_locale_and_english_fallback(self):
        self.assertEqual(language({}, 'ru_RU'), 'ru')
        self.assertEqual(language({'LC_ALL': 'C.UTF-8'}, 'ru_RU'), 'ru')
        self.assertEqual(language({}, 'de_DE'), 'en')
        self.assertEqual(language({}, ''), 'en')

    def test_locale_environment_precedence(self):
        environment = {'LANG': 'ru_RU.UTF-8', 'LC_MESSAGES': 'en_US.UTF-8'}
        self.assertEqual(language(environment, 'ru_RU'), 'en')
        environment['LC_ALL'] = 'ru_RU.UTF-8'
        self.assertEqual(language(environment, 'en_US'), 'ru')

    def test_text_and_runtime_environment(self):
        self.assertEqual(text('English', 'Русский', 'en'), 'English')
        self.assertEqual(text('English', 'Русский', 'ru'), 'Русский')
        self.assertEqual(runtime_environment({'OPENSHSM_LANGUAGE': 'ru'}),
            {'OPENSHSM_LANGUAGE': 'ru'})


if __name__ == '__main__':
    unittest.main()
