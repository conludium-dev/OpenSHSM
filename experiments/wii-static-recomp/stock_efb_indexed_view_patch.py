"""Preserve native intensity-copy sampling through the existing texture cache."""
from pathlib import Path
from stock_gx_renderer_texgen_patch import replace_once


def header(text):
    marker = 'class TextureCache {\n'
    structs = '''struct CachedTexture {
    GLuint texture = 0;
    uint64_t efb_revision = 0;
    uint32_t palette_hash = 0;
};

struct EfbCopyTexture {
    GLuint texture = 0;
    uint32_t width = 0;
    uint32_t height = 0;
    uint32_t valid_height = 0;
    uint32_t source_x = 0;
    uint32_t source_y = 0;
    uint32_t control = 0;
    uint32_t pixel_format = 0;
    uint32_t filter0 = 0;
    uint32_t filter1 = 0;
    uint64_t revision = 0;

    bool indexed_view(const gx::TexStage& stage) const {
        const unsigned raw_format = (control >> 3) & 15;
        const unsigned format = (raw_format >> 1) | ((raw_format & 1) << 3);
        return texture && stage.format == 9 && stage.tlut_format <= 2
            && (format == 1 || format == 8) && (control & 0x18000) == 0x18000
            && !(control & (0x200 | 0x180 | 0x4000)) && pixel_format <= 2
            && source_x == 0 && source_y == 0 && width == stage.width && width > 0 && width <= 640
            && height >= 528
            && stage.height > 0 && stage.height <= height && stage.height <= valid_height;
    }
};

'''
    text = replace_once(text, marker, structs + marker)
    text = replace_once(text, '    void register_efb_texture(uint32_t addr, GLuint tex);',
        '    void register_efb_texture(uint32_t addr, GLuint tex);\n'
        '    void register_efb_texture(uint32_t addr, GLuint tex, const EfbCopyTexture& copy);')
    text = replace_once(text, '    TextureCache() = default;',
        '    TextureCache() = default;\n    void evict_unbound();')
    text = replace_once(text, 'std::unordered_map<TextureKey, GLuint, TextureKeyHash> cache;',
        'std::unordered_map<TextureKey, CachedTexture, TextureKeyHash> cache;')
    text = replace_once(text, 'std::unordered_map<uint32_t, GLuint> efb_textures;',
        'std::unordered_map<uint32_t, EfbCopyTexture> efb_textures;')
    return text + '''
namespace nwii::runtime::gx {
void RenderIndexedEfbCopy(GLuint source, GLuint target, const TexStage& stage,
    const hle::EfbCopyTexture& copy, const Color* palette, bool allocate);
}
'''


def texture(text):
    text = replace_once(text, '#include <algorithm>', '#include <array>\n#include <stdexcept>\n#include <algorithm>')
    text = text.replace('&pair.second)', '&pair.second.texture)')
    before = '''void TextureCache::register_efb_texture(uint32_t addr, GLuint tex) {
    efb_textures[addr & 0x3FFFFFFF] = tex;
}'''
    text = replace_once(text, before, '''void TextureCache::register_efb_texture(uint32_t addr, GLuint tex) {
    register_efb_texture(addr, tex, EfbCopyTexture{});
}

void TextureCache::register_efb_texture(uint32_t addr, GLuint tex, const EfbCopyTexture& copy) {
    auto& entry = efb_textures[addr & 0x3FFFFFFF];
    const uint64_t revision = entry.revision + 1;
    entry = copy;
    entry.texture = tex;
    entry.revision = revision ? revision : 1;
}''')
    text = replace_once(text, 'return it == efb_textures.end() ? 0 : it->second;',
        'return it == efb_textures.end() ? 0 : it->second.texture;')
    start = text.index('    if (cache.size() > 512) {')
    end = text.index('\n\n    const auto source_before', start)
    eviction = text[start:end].replace('item->second', 'item->second.texture')
    text = text[:start] + '    evict_unbound();' + text[end:]
    marker = 'GLuint TextureCache::get_texture(CPUContext& ctx, const gx::TexStage& stage) {'
    text = replace_once(text, marker, 'static inline Color unpack_rgb565(uint16_t);\nstatic inline Color unpack_rgb5a3(uint16_t);\n\nvoid TextureCache::evict_unbound() {\n' + eviction + '\n}\n\n' + marker)
    before = '''    if (GLuint efb = find_efb_texture(stage.base_addr))
        return efb;'''
    after = '''    auto efb = efb_textures.find(stage.base_addr & 0x3FFFFFFF);
    if (efb != efb_textures.end()) {
        const auto& copy = efb->second;
        if (!copy.indexed_view(stage)) {
            return copy.texture;
        }
        std::array<Color, 256> palette{};
        uint32_t hash = 2166136261u;
        for (unsigned index = 0; index < palette.size(); ++index) {
            const uint64_t offset = uint64_t(stage.tlut_offset) + index * 2;
            Color color = MAGENTA;
            if (offset + 1 < sizeof(g_state.tlutMem)) {
                const uint8_t high = g_state.tlutMem[offset];
                const uint8_t low = g_state.tlutMem[offset + 1];
                const uint16_t entry = uint16_t(high) << 8 | low;
                if (stage.tlut_format == 0) {
                    color = {low, low, low, high};
                } else if (stage.tlut_format == 1) {
                    color = unpack_rgb565(entry);
                } else {
                    color = unpack_rgb5a3(entry);
                }
            }
            palette[index] = color;
            for (uint8_t channel : {color.r, color.g, color.b, color.a}) {
                hash = (hash ^ channel) * 16777619u;
            }
        }
        TextureKey key{stage.base_addr & 0x3FFFFFFF, stage.width, stage.height,
            stage.format, stage.tlut_offset, stage.tlut_format, 0};
        auto view = cache.find(key);
        const bool allocate = view == cache.end();
        if (allocate) {
            evict_unbound();
            GLuint texture = 0;
            glGenTextures(1, &texture);
            if (!texture) {
                throw std::runtime_error("GX indexed EFB view texture unavailable");
            }
            view = cache.emplace(key, CachedTexture{texture, 0, 0}).first;
        }
        auto& value = view->second;
        if (allocate || value.efb_revision != copy.revision || value.palette_hash != hash) {
            gx::RenderIndexedEfbCopy(copy.texture, value.texture, stage, copy, palette.data(), allocate || value.efb_revision == 0);
            value.efb_revision = copy.revision;
            value.palette_hash = hash;
        }
        return value.texture;
    }'''
    text = replace_once(text, before, after)
    text = replace_once(text, '        return it->second;\n', '        return it->second.texture;\n')
    return replace_once(text, '    cache[key] = tex;', '    cache[key] = CachedTexture{tex, 0, 0};')


def renderer(text):
    marker = 'static void DiagnoseGL(const char* phase) {\n'
    helper = Path(__file__).with_name('stock_efb_indexed_view.inc').read_text()
    text = replace_once(text, marker, helper + '\n' + marker)
    before = '''            nwii::runtime::hle::TextureCache::get().register_efb_texture(dest,
                                                                         tex);'''
    after = '''            nwii::runtime::hle::EfbCopyTexture copy;
            copy.width = copy_w;
            copy.height = copy_h;
            copy.valid_height = g_state.efbSrcY < 528 ? std::min(copy_h, 528u - g_state.efbSrcY) : 0;
            copy.source_x = g_state.efbSrcX;
            copy.source_y = g_state.efbSrcY;
            copy.control = cmd.val;
            copy.pixel_format = g_state.bp[0x43] & 7;
            copy.filter0 = g_state.bp[0x53];
            copy.filter1 = g_state.bp[0x54];
            nwii::runtime::hle::TextureCache::get().register_efb_texture(dest, tex, copy);'''
    return replace_once(text, before, after)
