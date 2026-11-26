"""Backport SDL2's opt-out hint for the macOS GameController backend to pinned SDL 2.28.5."""
from pathlib import Path
import argparse


def adapt(source):
    before = source
    for name in ('static int IOS_JoystickInit(void)', 'SDL_bool IOS_SupportedHIDDevice(IOHIDDeviceRef device)'):
        site = name + '\n{\n'
        replacement = site + '    if (!SDL_GetHintBoolean("SDL_JOYSTICK_MFI", SDL_TRUE)) {\n        return 0;\n    }\n\n'
        if replacement in source:
            continue
        if source.count(site) != 1:
            raise ValueError('Pinned SDL MFI hint site differs: ' + name)
        source = source.replace(site, replacement, 1)
    if before == source and source.count('SDL_GetHintBoolean("SDL_JOYSTICK_MFI", SDL_TRUE)') != 2:
        raise ValueError('SDL MFI hint patch differs')
    return source


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    original = args.source.read_text()
    patched = adapt(original)
    if original != patched:
        args.source.write_text(patched)
