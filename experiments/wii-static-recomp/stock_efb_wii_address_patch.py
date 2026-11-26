"""Preserve Wii MEM2 bank bits in the existing EFB texture and retile maps."""


def adapt(source, name):
    before, after = {
        'src/hle/texture_cache_gl.cpp': ('addr & 0x01FFFFFF', 'addr & 0x3FFFFFFF'),
        'src/hle/gx/renderer_gl.cpp': ('dest & 0x01ffffffu', 'dest & 0x3fffffffu'),
    }[name]
    text = source.decode()
    if text.count(before) != 2 or after in text:
        raise ValueError('Existing EFB address key sites differ: ' + name)
    return text.replace(before, after).encode()
