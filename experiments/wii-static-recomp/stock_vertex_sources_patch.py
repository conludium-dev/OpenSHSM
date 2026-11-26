"""Retain raw attributes on the existing deferred draw, without changing VertexData."""
from stock_vertex_uv_patch import adapt as adapt_uv


def adapt_header(text):
    before = '    std::vector<uint8_t> bytes;\n};'
    assert text.count(before) == 1
    return '#include "stock_gx_vertex_sources.h"\n' + text.replace(before,
        '    std::vector<uint8_t> bytes;\n'
        '    std::vector<openshsm::experiment::GxVertexSources> sources;\n};', 1)


def adapt(text):
    text = adapt_uv(text)
    shift_divisor = '(float)(1 << shift)'
    assert text.count(shift_divisor) == 5
    text = text.replace(shift_divisor, 'float(uint32_t(1) << shift)')
    start = text.index('void FifoParser::DecodeDraw')
    end = text.index('\nvoid FifoParser::Parse(', start)
    body = text[start:end]
    replacements = [
        ('    const DrawRaw& r = *c.raw;',
         '    if (c.raw.use_count() > 1) {\n'
         '        c.raw = std::make_shared<DrawRaw>(*c.raw);\n'
         '    }\n'
         '    DrawRaw& r = *c.raw;\n    r.sources.clear();\n    r.sources.reserve(r.count);'),
        ('        VertexData vtx;', '        VertexData vtx{};\n        openshsm::experiment::GxVertexSources source;'),
        ('        if (r.vat.nrmMask != VtxAttrMask::None && r.need_normal) {',
         '        if (r.vat.nrmMask != VtxAttrMask::None) {'),
        ('            if (!ReadVectorAttr(buf, off, buf_size, r.vat.nrmMask, r.vat.nrmType,\n'
         '                                0, r.arrayBase[1], r.arrayStride[1],\n'
         '                                r.vat.nrmElements ? 9 : 3, nbt))\n'
         '                return;\n'
         '            if (nrm_idx3) off += 2 * nrm_idx_bytes;',
         '            const unsigned shifts[] = {7, 6, 15, 14, 0, 0, 0, 0};\n'
         '            const unsigned type = unsigned(r.vat.nrmType);\n'
         '            if (type >= 8) { return; }\n'
         '            if (nrm_idx3) {\n'
         '                for (unsigned normal = 0; normal < 3; ++normal) {\n'
         '                    const uint64_t base = uint64_t(r.arrayBase[1]) + normal * 3 * TypeSize(r.vat.nrmType);\n'
         '                    if (base > UINT32_MAX || !ReadVectorAttr(buf, off, buf_size, r.vat.nrmMask,\n'
         '                            r.vat.nrmType, shifts[type], uint32_t(base), r.arrayStride[1], 3, nbt + normal * 3)) {\n'
         '                        return;\n'
         '                    }\n'
         '                }\n'
         '            } else if (!ReadVectorAttr(buf, off, buf_size, r.vat.nrmMask, r.vat.nrmType,\n'
         '                    shifts[type], r.arrayBase[1], r.arrayStride[1], r.vat.nrmElements ? 9 : 3, nbt)) {\n'
         '                return;\n'
         '            }'),
        ('            vtx.norm[0] = nbt[0]; vtx.norm[1] = nbt[1]; vtx.norm[2] = nbt[2];',
         '            vtx.norm[0] = nbt[0]; vtx.norm[1] = nbt[1]; vtx.norm[2] = nbt[2];\n'
         '            source.has_normal = true;\n'
         '            source.has_nbt = r.vat.nrmElements;\n'
         '            for (unsigned normal = 0; normal < (source.has_nbt ? 3u : 1u); ++normal) {\n'
         '                std::copy_n(nbt + normal * 3, 3, source.normals[normal].begin());\n'
         '            }'),
        ('        off += AttrBytes(r.vat.clrMask[1], r.vat.clrType[1], 1, true);',
         '        source.has_color[0] = vtx.has_color;\n'
         '        std::copy_n(vtx.color, 4, source.colors[0].begin());\n'
         '        if (r.vat.clrMask[1] != VtxAttrMask::None) {\n'
         '            if (!ReadColorAttr(buf, off, buf_size, r.vat.clrMask[1], r.vat.clrType[1],\n'
         '                    r.arrayBase[3], r.arrayStride[3], source.colors[1].data())) {\n'
         '                return;\n'
         '            }\n'
         '            source.has_color[1] = true;\n'
         '        }'),
        ('        if (off > buf_size)\n            return;',
         '        if (off > buf_size) {\n            return;\n        }\n'
         '        std::copy_n(vtx.pos, 3, source.position.begin());\n'
         '        source.has_position = vtx.has_pos;\n'
         '        for (unsigned slot = 0; slot < 8; ++slot) {\n'
         '            std::copy_n(vtx.tex[slot], 2, source.uv[slot].begin());\n'
         '            source.has_uv[slot] = vtx.has_tex[slot];\n'
         '            source.matrix_indices[slot] = vtx.texMtxIdx[slot];\n'
         '        }'),
        ('        c.vertices.push_back(vtx);', '        r.sources.push_back(source);\n        c.vertices.push_back(vtx);'),
        ('    c.raw.reset(); // decoded: drop the raw copy', '    std::vector<uint8_t>().swap(r.bytes);')]
    for before, after in replacements:
        assert body.count(before) == 1, before
        body = body.replace(before, after, 1)
    body = body.replace('        // CLR1 is skipped; normals are decoded only for lit draws.\n', '')
    text = text[:start] + body + text[end:]
    vector_before = '''        if (!nwii::runtime::g_mmu) return true;
        uint32_t base = array_base + index * array_stride;

        

        const uint8_t* p = nwii::runtime::g_mmu->get_ptr(base);
        if (!p) return true;'''
    vector_after = '''        if (!nwii::runtime::g_mmu) { return false; }
        const uint64_t base = uint64_t(array_base) + uint64_t(index) * array_stride;
        if (base > UINT32_MAX) { return false; }
        const uint8_t* p = openshsm::experiment::gx_attribute_pointer(*nwii::runtime::g_mmu,
            uint32_t(base), size_t(sz) * ncomp);
        if (!p) { return false; }'''
    color_before = '''        if (!nwii::runtime::g_mmu) return true;
        uint32_t base = array_base + index * array_stride;
        const uint8_t* p = nwii::runtime::g_mmu->get_ptr(base);
        if (!p) return true;'''
    color_after = '''        if (!nwii::runtime::g_mmu) { return false; }
        const uint64_t base = uint64_t(array_base) + uint64_t(index) * array_stride;
        if (base > UINT32_MAX) { return false; }
        const uint8_t* p = openshsm::experiment::gx_attribute_pointer(*nwii::runtime::g_mmu,
            uint32_t(base), size_t(nbytes));
        if (!p) { return false; }'''
    for before, after in ((vector_before, vector_after), (color_before, color_after)):
        assert text.count(before) == 1
        text = text.replace(before, after, 1)
    return '#include <algorithm>\n#include "stock_gx_attribute_bounds.h"\n' + text
