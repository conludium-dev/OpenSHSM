"""Select Russian or English for OpenSHSM desktop UI."""
import locale
import os
import plistlib
import subprocess
import sys
from functools import lru_cache


def _normalized(value):
    return value.strip().lower().replace('_', '-').split('.', 1)[0]


@lru_cache(maxsize=1)
def _preferred_locale():
    if sys.platform == 'darwin':
        try:
            result = subprocess.run(['/usr/bin/defaults', 'export', 'NSGlobalDomain', '-'],
                check=True, capture_output=True, timeout=2)
            languages = plistlib.loads(result.stdout).get('AppleLanguages', [])
            if languages:
                return languages[0]
        except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException,
                AttributeError, TypeError, ValueError):
            pass
    try:
        return locale.getlocale()[0] or ''
    except (TypeError, ValueError):
        return ''


def language(environment=None, locale_name=None):
    environment = os.environ if environment is None else environment
    override = _normalized(environment.get('OPENSHSM_LANGUAGE', ''))
    if override.startswith('ru'):
        return 'ru'
    if override.startswith('en'):
        return 'en'
    selected_locale = next((environment.get(name, '')
        for name in ('LC_ALL', 'LC_MESSAGES', 'LANG') if environment.get(name)), '')
    if _normalized(selected_locale) in ('c', 'posix'):
        selected_locale = ''
    selected_locale = selected_locale or (locale_name if locale_name is not None else _preferred_locale())
    return 'ru' if _normalized(selected_locale).startswith('ru') else 'en'


def text(english, russian, selected=None):
    return russian if (selected or language()) == 'ru' else english


def runtime_environment(environment=None):
    return {'OPENSHSM_LANGUAGE': language(environment)}
