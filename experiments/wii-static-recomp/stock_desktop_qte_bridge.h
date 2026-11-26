#pragma once
#include "stock_desktop_look.h"
#include "stock_desktop_qte.h"
#include "stock_desktop_qte_gui.h"
#include "stock_desktop_qte_bank.h"
#include "stock_desktop_qte_quad.h"
#include <processor_adapter.h>
#include <runtime/config.h>
#if __has_include("openshsm_owner_qte_payload.h")
#include "openshsm_owner_qte_payload.h"
#endif

namespace openshsm::experiment {

inline bool desktop_qte_guest_span(uint32_t address, uint32_t bytes) {
    return (address & 3u) == 0
        && ((address >= 0x80000000 && uint64_t(address) + bytes <= 0x81800000)
            || (address >= 0x90000000 && uint64_t(address) + bytes <= 0x94000000));
}

class DesktopQTERuntime {
public:
    void synchronize(nwii::runtime::CPUContext& ctx, bool desktop, uint64_t dropped,
        uint32_t now = desktop_look_time_ms()) {
        uint32_t player = 0, entity = 0;
        unsigned slot = 4;
        bool special = false, window = false;
        if (desktop && nwii::runtime::Config::get().input_mode == 6 && ctx.gpr[13] == 0x8052E720) {
            player = ctx.mmu.read32(0x80491B4C);
            const uint32_t controller = ctx.mmu.read32(0x80529160);
            const uint32_t gui = ctx.mmu.read32(0x80529D20);
            const bool gui_allowed = gui == 0 || (desktop_qte_guest_span(gui, 0x9B4)
                && ctx.mmu.read32(gui + 0x694) == 0 && ctx.mmu.read32(gui + 0x9B0) == 0);
            if (desktop_qte_guest_span(player, 0x2368) && gui_allowed
                && desktop_qte_guest_span(controller, 0x513A) && ctx.mmu.read8(controller + 0x5139) == 0) {
                const unsigned count = ctx.mmu.read32(player + 0x1388);
                special = ctx.mmu.read8(player + 0x6E4) != 0;
                window = special && ctx.mmu.read8(player + 0x156E) != 0;
                const unsigned active_slot = special ? ctx.mmu.read32(player + 0x6E8) : 4;
                unsigned attached = 0;
                bool valid = count > 0 && count <= 4;
                for (unsigned i = 0; i < 4; ++i) {
                    const uint32_t enemy = ctx.mmu.read32(player + 0x12C8 + i * 0x24);
                    if (enemy != 0) {
                        ++attached;
                        valid &= desktop_qte_guest_span(enemy, 0x30);
                        if ((!special && slot == 4) || (special && active_slot == i)) {
                            entity = enemy;
                            slot = i;
                        }
                    }
                }
                if (!valid || attached != count) {
                    slot = 4;
                }
            }
        }
        if (slot == 4) {
            disconnect(now);
            return;
        }
        if (player != owner || entity != enemy_owner || slot != target || special != special_mode || context == 0) {
            owner = player;
            enemy_owner = entity;
            target = slot;
            sequence = (sequence + 1) & DesktopQTEPromptChannel::max_context;
            if (sequence == 0) {
                sequence = 1;
            }
            context = sequence;
            state.enter(context, target);
            latest = {};
            requested = -1;
            controller_id = -1;
            special_mode = special;
            window_open = false;
        }
        if (window != window_open) {
            state.reset_input();
            latest = {};
            if (window) {
                state.rearm();
                window_since = now;
            }
            window_open = window;
        }
        if (dropped != last_dropped) {
            state.reset_input();
        }
        if (!special_mode && ctx.mmu.read32(owner + 0x1574) == 4 && ctx.mmu.read8(owner + 0x1571) == 0) {
            state.rearm();
        }
        last_dropped = dropped;
        primary_desktop_look_input().publish_qte(context, now);
        present_prompt(now);
    }

    void consume(const DesktopLookSample& sample, uint64_t generation) {
        if (generation <= last_generation) {
            return;
        }
        if (last_generation != 0 && generation != last_generation + 1) {
            state.reset_input();
        }
        last_generation = generation;
        if (sample.qte_controller != controller_id) {
            state.reset_input();
            controller_id = sample.qte_controller;
        }
        latest = sample;
        const bool valid = sample.qte_context == context && context != 0
            && sample.qte_controller >= -1 && (sample.qte_buttons & 0xF0) == 0
            && sample.device <= DesktopInputDevice::Gamepad
            && (!special_mode || (window_open && uint32_t(sample.time_ms - window_since) < 0x80000000u));
        latest.focused &= valid;
        state.consume(sample.qte_buttons, latest.focused, sample.time_ms, generation);
    }

    void apply(nwii::runtime::CPUContext& ctx, uint32_t now = desktop_look_time_ms()) {
        if (special_mode || ctx.gpr[18] != 0) {
            return;
        }
        requested = -1;
        if (!current(ctx) || ctx.gpr[15] != owner || !latest.focused || uint32_t(now - latest.time_ms) > 250
            || !primary_desktop_qte_prompt().shown(context, now)) {
            state.reset_input();
            return;
        }
        requested = state.request(now);
        for (unsigned i = 0; i < 4; ++i) {
            ctx.mmu.write8(owner + 0x1360 + i * 12, requested == int(i));
        }
        present_prompt(now);
    }

    int ttgrab(nwii::runtime::CPUContext& ctx, uint32_t now = desktop_look_time_ms()) {
        if (!special_mode || !window_open || !current(ctx) || ctx.gpr[14] != 0x804574F0
            || ctx.mmu.read8(owner + 0x156E) == 0) {
            return -1;
        }
        if (!latest.focused || uint32_t(now - latest.time_ms) > 250
            || !primary_desktop_qte_prompt().shown(context, now)) {
            state.reset_input();
            return 0;
        }
        const bool accepted = state.request(now) >= 0;
        if (accepted) {
            state.acknowledge();
        }
        present_prompt(now);
        return accepted;
    }

    void finish(nwii::runtime::CPUContext& ctx) {
        if (requested >= 0 && current(ctx) && desktop_qte_guest_span(ctx.gpr[1], 0x2C)
            && (ctx.mmu.read8(ctx.gpr[1] + 0x28 + unsigned(requested)) != 0
                || ctx.mmu.read32(owner + 0x1574) == unsigned(requested))) {
            state.acknowledge();
        }
        requested = -1;
    }

    // Configure from the guest CPU thread with a verified, stable generated payload.
    bool gui_bank_payload(const uint8_t* bytes, uint32_t size, const std::array<uint8_t, 16>& guid) {
        uint8_t nonzero = 0;
        for (uint8_t value : guid) {
            nonzero |= value;
        }
        if (!gui_bank.empty() || bank_release || bytes == nullptr || size == 0 || size > 65536 || nonzero == 0) {
            return false;
        }
        bank_bytes = bytes;
        bank_size = size;
        bank_guid = guid;
        return true;
    }

    void gui_bank_unload() {
        bank_bytes = nullptr;
        bank_size = 0;
        bank_release = true;
    }

    uint32_t gui_bank_handle() const {
        return gui_bank.handle();
    }

    bool gui_reset(nwii::runtime::CPUContext& ctx) {
        if (gui_quad.pending()) {
            return false;
        }
        if (gui_bank.resume(ctx)) {
            return true;
        }
        if (gui_bank.pending()) {
            return false;
        }
        if (bank_release) {
            if (gui_bank.handle() != 0) {
                if (gui_bank.release(ctx, ctx.pc)) {
                    return true;
                }
            } else if (gui_bank.empty()) {
                bank_release = false;
            }
        }
        if (gui_pass(ctx).record == 0) {
            gui_scope.reset();
            if (!bank_release && bank_bytes != nullptr && gui_allowed(ctx)
                && gui_bank.begin(ctx, ctx.pc, bank_bytes, bank_size, bank_guid)) {
                return true;
            }
        }
        return false;
    }

    bool gui_draw(nwii::runtime::CPUContext& ctx) {
        if (gui_quad.pending()) {
            gui_quad.resume(ctx);
            return false;
        }
        const auto pass = gui_pass(ctx);
        if (bank_release || pass.record == 0 || pass.return_pc != 0x800EBA90
            || (latest.device != DesktopInputDevice::KeyboardMouse && latest.device != DesktopInputDevice::Gamepad)) {
            return false;
        }
        const unsigned glyph = target + (latest.device == DesktopInputDevice::KeyboardMouse ? 4 : 0);
        return gui_quad.begin(ctx, pass, gui_bank.handle(), glyph);
    }

    bool gui_draw_pending() const {
        return gui_quad.pending();
    }

    void gui_enter_primary(nwii::runtime::CPUContext& ctx) {
        gui_scope.enter(ctx, ctx.gpr[28], ctx.gpr[29], 0x800EBA90, context, gui_allowed(ctx));
    }

    void gui_leave_primary(nwii::runtime::CPUContext& ctx) {
        gui_scope.leave(ctx, 0x800EBA90);
    }

    void gui_enter_secondary(nwii::runtime::CPUContext& ctx) {
        gui_scope.enter(ctx, ctx.gpr[30], ctx.gpr[31], 0x800EC6F0, context, gui_allowed(ctx));
    }

    void gui_leave_secondary(nwii::runtime::CPUContext& ctx) {
        gui_scope.leave(ctx, 0x800EC6F0);
    }

    DesktopQTEGuiPass gui_pass(nwii::runtime::CPUContext& ctx) const {
        return gui_scope.current(ctx, context, gui_allowed(ctx));
    }

    void disconnect(uint32_t now = desktop_look_time_ms()) {
        gui_scope.reset();
        state.enter(0, 4);
        context = owner = enemy_owner = 0;
        target = 4;
        requested = -1;
        latest = {};
        special_mode = window_open = false;
        primary_desktop_look_input().publish_qte(0, now);
        primary_desktop_qte_prompt().publish(0, 4, false, now);
    }

private:
    void present_prompt(uint32_t now) {
        primary_desktop_qte_prompt().publish(!special_mode || window_open ? context : 0,
            target, state.remaining_ms(now) != 0, now, latest.device);
    }

    bool current(nwii::runtime::CPUContext& ctx) const {
        return ctx.gpr[17] == owner && current_owner(ctx);
    }

    bool gui_allowed(nwii::runtime::CPUContext& ctx) const {
        const uint32_t now = desktop_look_time_ms();
        const auto prompt = primary_desktop_qte_prompt().read(now);
        return current_owner(ctx) && latest.focused && !latest.suspended
            && latest.qte_context == context && uint32_t(now - latest.time_ms) <= 250
            && latest.device != DesktopInputDevice::Unknown
            && prompt.context == context && prompt.target == target && prompt.device == latest.device;
    }

    bool current_owner(nwii::runtime::CPUContext& ctx) const {
        if (context == 0 || nwii::runtime::Config::get().input_mode != 6
            || ctx.gpr[13] != 0x8052E720
            || ctx.mmu.read32(0x80491B4C) != owner
            || (ctx.mmu.read8(owner + 0x6E4) != 0) != special_mode
            || (special_mode && ctx.mmu.read32(owner + 0x6E8) != target)
            || ctx.mmu.read32(owner + 0x12C8 + target * 0x24) != enemy_owner
            || ctx.mmu.read32(owner + 0x1388) == 0) {
            return false;
        }
        const uint32_t controller = ctx.mmu.read32(0x80529160);
        const uint32_t gui = ctx.mmu.read32(0x80529D20);
        return desktop_qte_guest_span(controller, 0x513A) && ctx.mmu.read8(controller + 0x5139) == 0
            && (gui == 0 || (desktop_qte_guest_span(gui, 0x9B4)
                && ctx.mmu.read32(gui + 0x694) == 0 && ctx.mmu.read32(gui + 0x9B0) == 0));
    }

    DesktopQTEState state;
    DesktopQTEGuiScope gui_scope;
    DesktopQTEBank gui_bank;
    DesktopQTEQuad<nwii::runtime::CPUContext> gui_quad;
#ifdef OPENSHSM_OWNER_QTE_PAYLOAD
    const uint8_t* bank_bytes = prepared_qte::bytes;
    uint32_t bank_size = sizeof(prepared_qte::bytes);
    std::array<uint8_t, 16> bank_guid = prepared_qte::guid;
#else
    const uint8_t* bank_bytes = nullptr;
    uint32_t bank_size = 0;
    std::array<uint8_t, 16> bank_guid{};
#endif
    bool bank_release = false;
    DesktopLookSample latest{};
    uint32_t owner = 0, enemy_owner = 0, context = 0, sequence = 0;
    uint32_t window_since = 0;
    unsigned target = 4;
    int requested = -1;
    int32_t controller_id = -1;
    uint64_t last_generation = 0, last_dropped = 0;
    bool special_mode = false, window_open = false;
};

inline DesktopQTERuntime& primary_desktop_qte_runtime() {
    static DesktopQTERuntime runtime;
    return runtime;
}

}
