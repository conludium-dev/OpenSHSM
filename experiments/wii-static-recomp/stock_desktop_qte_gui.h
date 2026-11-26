#pragma once
#include <array>
#include <cstdint>

namespace openshsm::experiment {

struct DesktopQTEGuiPass {
    uint32_t manager = 0, record = 0, root = 0, page = 0;
    uint32_t context = 0, stack = 0, return_pc = 0, begin = 0, end = 0;
};

// The caller validates the desktop prompt on entry and every query, and resets at a new outer GUI pass.
class DesktopQTEGuiScope {
public:
    void reset() {
        depth = 0;
        blocked = false;
    }

    template<class Context>
    void enter(Context& ctx, uint32_t manager, uint32_t record, uint32_t return_pc,
        uint32_t context, bool allowed) {
        if (blocked) {
            return;
        }
        if (depth == frames.size()) {
            reset();
            blocked = true;
            return;
        }
        auto& frame = frames[depth++];
        frame = {};
        frame.stack = ctx.gpr[1];
        frame.return_pc = return_pc;
        if (!allowed || context == 0 || ctx.gpr[13] != 0x8052E720
            || (return_pc != 0x800EBA90 && return_pc != 0x800EC6F0)
            || !span(manager, 0x1DAC) || ctx.mmu.read32(0x80529D20) != manager
            || !span(record, 36) || !span(frame.stack, 8)) {
            return;
        }
        frame.manager = manager;
        frame.begin = ctx.mmu.read32(manager + 0x1DA4);
        frame.end = ctx.mmu.read32(manager + 0x1DA8);
        if (!record_span(frame, record)) {
            frame.manager = 0;
            return;
        }
        frame.root = ctx.mmu.read32(record + 0x14);
        frame.page = ctx.mmu.read32(record + 0x1C);
        if (frame.root != ctx.gpr[3] || !span(frame.root, 0x5C)
            || ctx.mmu.read32(frame.root) != 0x803F4BF0 || frame.page < 55 || frame.page > 57) {
            frame.manager = 0;
            return;
        }
        frame.record = record;
        frame.context = context;
    }

    template<class Context>
    void leave(Context& ctx, uint32_t return_pc) {
        if (blocked || depth == 0) {
            return;
        }
        const auto& frame = frames[depth - 1];
        if (ctx.gpr[1] != frame.stack || frame.return_pc != return_pc) {
            reset();
            return;
        }
        --depth;
    }

    template<class Context>
    DesktopQTEGuiPass current(Context& ctx, uint32_t context, bool allowed) const {
        if (blocked || depth == 0 || !allowed || context == 0 || ctx.gpr[13] != 0x8052E720) {
            return {};
        }
        const auto& frame = frames[depth - 1];
        if (frame.manager == 0 || frame.context != context
            || ctx.mmu.read32(0x80529D20) != frame.manager
            || ctx.mmu.read32(frame.manager + 0x1DA4) != frame.begin
            || ctx.mmu.read32(frame.manager + 0x1DA8) != frame.end
            || ctx.mmu.read32(frame.record + 0x14) != frame.root
            || ctx.mmu.read32(frame.record + 0x1C) != frame.page) {
            return {};
        }
        uint32_t stack = ctx.gpr[1];
        for (unsigned i = 0; i < 64 && stack < frame.stack; ++i) {
            if (!span(stack, 8)) {
                return {};
            }
            const uint32_t next = ctx.mmu.read32(stack);
            if (next <= stack || next > frame.stack) {
                return {};
            }
            stack = next;
            if (stack == frame.stack && ctx.mmu.read32(stack + 4) == frame.return_pc) {
                return frame;
            }
        }
        return {};
    }

private:
    static bool span(uint32_t address, uint32_t bytes) {
        return (address & 3u) == 0
            && ((address >= 0x80000000 && uint64_t(address) + bytes <= 0x81800000)
                || (address >= 0x90000000 && uint64_t(address) + bytes <= 0x94000000));
    }

    static bool record_span(const DesktopQTEGuiPass& frame, uint32_t record) {
        return frame.end >= frame.begin && span(frame.begin, frame.end - frame.begin)
            && (frame.end - frame.begin) % 36 == 0 && record >= frame.begin
            && uint64_t(record) + 36 <= frame.end && (record - frame.begin) % 36 == 0;
    }

    std::array<DesktopQTEGuiPass, 8> frames{};
    unsigned depth = 0;
    bool blocked = false;
};

}
