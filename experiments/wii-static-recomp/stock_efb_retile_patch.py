"""Adapt RGBA8 EFB copies that reinterpret the same Wii tiled bytes at a new width."""
from pathlib import Path
import hashlib


BASE_SHA256 = '3efcf70442ff3fcde31e072b2398a6f639f0736f0071c21fabe1e5fc8189d1a0'
OUTPUT_SHA256 = '882785e8bdc85e030453297a70937c72484ec8975ecb382fbcb78f06787ca6eb'
HELPER_ANCHOR = 'static void DiagnoseGL(const char* phase) {\n'
COPY_START = ('            GLuint tex =\n'
    '                nwii::runtime::hle::TextureCache::get().find_efb_texture(dest);\n')
COPY_END = '            const unsigned raw_format = (cmd.val >> 3) & 15;\n'


def adapt_renderer(source):
    if hashlib.sha256(source).hexdigest() != BASE_SHA256:
        raise ValueError('EFB retile input differs from verified graphics recovery')
    text = source.decode()
    if text.count(HELPER_ANCHOR) != 1 or text.count(COPY_START) != 1 or \
            text.count(COPY_END) != 1:
        raise ValueError('EFB retile patch site differs')
    root = Path(__file__).resolve().parent
    helper = (root / 'stock_efb_retile_helper.inc').read_text()
    copy = (root / 'stock_efb_retile_copy.inc').read_text()
    start = text.index(COPY_START)
    end = text.index(COPY_END, start)
    text = text[:start] + copy + text[end:]
    text = text.replace(HELPER_ANCHOR, helper + HELPER_ANCHOR, 1)
    output = text.encode()
    if hashlib.sha256(output).hexdigest() != OUTPUT_SHA256:
        raise RuntimeError('EFB retile output differs from verified source')
    return output
