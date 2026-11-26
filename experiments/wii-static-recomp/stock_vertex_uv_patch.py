"""Preserve all eight existing UV attributes in the retained deferred decoder."""


def adapt(text):
    start = text.index('        if (r.vat.texMask[0] != VtxAttrMask::None) {', text.index('void FifoParser::DecodeDraw'))
    end = text.index('        if (off > buf_size)', start)
    before = text[start:end]
    assert 'for (int t = 1; t < 8; t++)' in before
    after = '''        for (int t = 0; t < 8; ++t) {
            if (r.vat.texMask[t] != VtxAttrMask::None) {
                if (!ReadVectorAttr(buf, off, buf_size, r.vat.texMask[t],
                        r.vat.texType[t], r.vat.texShift[t],
                        r.arrayBase[4 + t], r.arrayStride[4 + t],
                        r.vat.texElements[t] ? 2 : 1, vtx.tex[t])) {
                    return;
                }
                vtx.has_tex[t] = true;
            }
        }
'''
    updated = text[:start] + after + text[end:]
    stale = '''        // CLR1 and tex1-7 are parsed for stream position only (the renderer
        // uses clr0/tex0). Normals are decoded only for lit draws.
'''
    assert updated.count(stale) == 1
    return updated.replace(stale, '        // CLR1 is skipped; normals are decoded only for lit draws.\n', 1)
