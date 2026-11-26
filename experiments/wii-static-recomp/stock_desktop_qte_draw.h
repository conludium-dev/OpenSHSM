#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace openshsm::experiment {

enum class DesktopQTEGroup { None, Pull, Push, LeftSwipe, RightSwipe, PullDown };

struct DesktopQTEGroupGeometry {
    DesktopQTEGroup group = DesktopQTEGroup::None;
    uint32_t node = 0;
    std::array<float, 4> bounds{};
    std::array<float, 6> affine{};
    float opacity = 0;

    bool drawable() const {
        if (group == DesktopQTEGroup::None || !std::isfinite(opacity) || opacity <= 0 || opacity > 1) {
            return false;
        }
        for (float value : bounds) {
            if (!std::isfinite(value)) {
                return false;
            }
        }
        for (float value : affine) {
            if (!std::isfinite(value)) {
                return false;
            }
        }
        return bounds[2] > bounds[0] && bounds[3] > bounds[1];
    }
};

struct DesktopQTEQuadBounds {
    std::array<float, 2> minimum{}, maximum{};
};

inline bool desktop_qte_upright_bounds(const DesktopQTEGroupGeometry& geometry,
    float edge, DesktopQTEQuadBounds& result) {
    if (!geometry.drawable() || !std::isfinite(edge) || edge <= 0) {
        return false;
    }
    const auto& b = geometry.bounds;
    const auto& m = geometry.affine;
    const float x = b[0] + (b[2] - b[0]) * 0.5f;
    const float y = b[1] + (b[3] - b[1]) * 0.5f;
    const float center_x = m[0] * x + m[5] * y + m[2];
    const float center_y = m[4] * x + m[1] * y + m[3];
    const float width = std::min(edge, b[2] - b[0]) * std::hypot(m[0], m[4]);
    const float height = std::min(edge, b[3] - b[1]) * std::hypot(m[5], m[1]);
    DesktopQTEQuadBounds candidate{{center_x - width * 0.5f, center_y - height * 0.5f},
        {center_x + width * 0.5f, center_y + height * 0.5f}};
    for (unsigned i = 0; i < 2; ++i) {
        if (!std::isfinite(candidate.minimum[i]) || !std::isfinite(candidate.maximum[i])
            || candidate.maximum[i] <= candidate.minimum[i]) {
            return false;
        }
    }
    result = candidate;
    return true;
}

inline bool desktop_qte_draw_span(uint32_t address, uint32_t bytes) {
    return (address & 3) == 0
        && ((address >= 0x80000000 && uint64_t(address) + bytes <= 0x81800000)
            || (address >= 0x90000000 && uint64_t(address) + bytes <= 0x94000000));
}

template<class Context>
uint32_t desktop_qte_bank_texture(Context& ctx, uint32_t resource, unsigned glyph) {
    static constexpr const char* names[] = {"OpenSHSM_QTE_PAD_CROSS", "OpenSHSM_QTE_PAD_TRIANGLE",
        "OpenSHSM_QTE_PAD_SQUARE", "OpenSHSM_QTE_PAD_CIRCLE", "OpenSHSM_QTE_KEY_UP",
        "OpenSHSM_QTE_KEY_DOWN", "OpenSHSM_QTE_KEY_LEFT", "OpenSHSM_QTE_KEY_RIGHT"};
    if (glyph >= 8 || !desktop_qte_draw_span(resource, 0x34)
        || ctx.mmu.read32(resource) != 0x8042B2EC || ctx.mmu.read32(resource + 0x1C) == 0) {
        return 0;
    }
    const uint32_t dictionary = ctx.mmu.read32(resource + 0x14);
    if (!desktop_qte_draw_span(dictionary, 16)) {
        return 0;
    }
    const uint32_t sentinel = dictionary + 8;
    uint32_t previous = sentinel, link = ctx.mmu.read32(sentinel), found = 0;
    unsigned seen = 0;
    for (unsigned count = 0; link != sentinel && count < 8; ++count) {
        const uint32_t texture = link - 8;
        if (!desktop_qte_draw_span(texture, 0x58) || ctx.mmu.read32(texture + 4) != dictionary
            || ctx.mmu.read32(texture + 0x54) == 0 || ctx.mmu.read32(link + 4) != previous) {
            return 0;
        }
        const uint32_t raster = ctx.mmu.read32(texture);
        if (!desktop_qte_draw_span(raster, 0x14) || ctx.mmu.read32(raster + 0x0C) != 32
            || ctx.mmu.read32(raster + 0x10) != 32) {
            return 0;
        }
        unsigned index = 0;
        for (; index < 8; ++index) {
            bool equal = true;
            for (unsigned character = 0; character < 32; ++character) {
                const uint8_t value = uint8_t(names[index][character]);
                if (ctx.mmu.read8(texture + 0x10 + character) != value) {
                    equal = false;
                    break;
                }
                if (value == 0) {
                    break;
                }
            }
            if (equal) {
                break;
            }
        }
        if (index == 8 || (seen & (1u << index)) != 0) {
            return 0;
        }
        seen |= 1u << index;
        if (index == glyph) {
            found = texture;
        }
        previous = link;
        link = ctx.mmu.read32(link);
    }
    return link == sentinel && previous == ctx.mmu.read32(sentinel + 4) && seen == 0xFF ? found : 0;
}

template<class Context>
DesktopQTEGroupGeometry desktop_qte_group_geometry(Context& ctx, uint32_t node,
    uint32_t root, uint32_t page, uint32_t affine, double inherited_opacity) {
    DesktopQTEGroupGeometry result;
    if (!desktop_qte_draw_span(node, 0x44) || !desktop_qte_draw_span(root, 8)
        || !desktop_qte_draw_span(affine, 24) || ctx.mmu.read32(node) != 0x803F46F0
        || ctx.mmu.read32(root) != 0x803F4BF0 || page < 55 || page > 57) {
        return result;
    }
    const uint32_t name = ctx.mmu.read32(node + 0x28);
    if (page == 57) {
        if (name == 0xB0855300) {
            result.group = DesktopQTEGroup::PullDown;
        }
    } else {
        switch (name) {
            case 0x825B6448: result.group = DesktopQTEGroup::Pull; break;
            case 0x92671EAB: result.group = DesktopQTEGroup::Push; break;
            case 0x7B13435E: result.group = DesktopQTEGroup::LeftSwipe; break;
            case 0x7F749671: result.group = DesktopQTEGroup::RightSwipe; break;
            default: break;
        }
    }
    if (result.group == DesktopQTEGroup::None) {
        return result;
    }
    uint32_t ancestor = node;
    for (unsigned depth = 0; ancestor != root; ++depth) {
        if (depth == 32 || !desktop_qte_draw_span(ancestor, 8)) {
            return {};
        }
        ancestor = ctx.mmu.read32(ancestor + 4);
    }
    result.node = node;
    for (unsigned i = 0; i < result.bounds.size(); ++i) {
        result.bounds[i] = ctx.mmu.read_f32(node + 0x34 + i * 4);
    }
    for (unsigned i = 0; i < result.affine.size(); ++i) {
        result.affine[i] = ctx.mmu.read_f32(affine + i * 4);
    }
    result.opacity = inherited_opacity * ctx.mmu.read_f32(node + 0x2C);
    return result;
}

}
