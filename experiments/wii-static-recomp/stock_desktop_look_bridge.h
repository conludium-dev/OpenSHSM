#pragma once
#include "stock_desktop_look.h"
#include <processor_adapter.h>
#include <runtime/config.h>
#include <cstdio>
#include <cstdlib>
#include <array>
#include <limits>

namespace openshsm::experiment {

inline bool desktop_look_guest_span(uint32_t address, uint32_t size) {
    return (address & 3u) == 0
        && ((address >= 0x80000000 && uint64_t(address) + size <= 0x81800000)
            || (address >= 0x90000000 && uint64_t(address) + size <= 0x94000000));
}

class DesktopLookTrace {
public:
    void capture(nwii::runtime::CPUContext& ctx, bool desktop, uint32_t now, bool enabled) {
        const uint32_t player = ctx.gpr[3];
        if (!enabled || count >= 64 || nwii::runtime::Config::get().input_mode != 6
            || ctx.gpr[13] != 0x8052E720 || !desktop_look_guest_span(player, 0x2368)
            || ctx.mmu.read32(0x80491B4C) != player) {
            return;
        }
        if (desktop) {
            owner = player;
        }
        if (owner != player) {
            return;
        }
        const uint32_t mode = ctx.mmu.read32(player + 0x1288);
        if (count != 0 && mode == last_mode && uint32_t(now - last_time) < 1000) {
            return;
        }
        last_mode = mode;
        last_time = now;
        ++count;
        std::printf("[DesktopAim] sample=%u time=%u player=%08x desktop=%u state=%u block=%u torch=%u pointer=%u weights=%g,%g target=%g,%g,%g origin=%g,%g,%g\n",
            count, now, player, unsigned(desktop), mode, ctx.mmu.read8(player + 0x14FD),
            ctx.mmu.read8(player + 0x1185), ctx.mmu.read8(player + 0x1569),
            ctx.mmu.read_f32(player + 0x20D0), ctx.mmu.read_f32(player + 0x235C),
            ctx.mmu.read_f32(player + 0x154C), ctx.mmu.read_f32(player + 0x1550), ctx.mmu.read_f32(player + 0x1554),
            ctx.mmu.read_f32(player + 0x1558), ctx.mmu.read_f32(player + 0x155C), ctx.mmu.read_f32(player + 0x1560));
        const uint32_t records = ctx.mmu.read32(player + 0x154);
        if (!desktop_look_guest_span(records, 8 * 188)) {
            return;
        }
        uint32_t observed_torch = 0;
        for (uint32_t slot = 0; slot < 4; ++slot) {
            const uint32_t record = records + slot * 188;
            const uint32_t source = ctx.mmu.read32(record + 156);
            const bool valid = desktop_look_guest_span(source, 64);
            std::printf("[DesktopMount] sample=%u slot=%u enabled=%u hold=%u boneField=%08x source=%08x worldAt=%g,%g,%g cachedAt=%g,%g,%g sourceAt=%g,%g,%g position=%g,%g,%g\n",
                count, slot, ctx.mmu.read8(record + 160), ctx.mmu.read8(record + 161), ctx.mmu.read32(record + 152), source,
                ctx.mmu.read_f32(record + 32), ctx.mmu.read_f32(record + 36), ctx.mmu.read_f32(record + 40),
                ctx.mmu.read_f32(record + 96), ctx.mmu.read_f32(record + 100), ctx.mmu.read_f32(record + 104),
                valid ? ctx.mmu.read_f32(source + 32) : 0, valid ? ctx.mmu.read_f32(source + 36) : 0,
                valid ? ctx.mmu.read_f32(source + 40) : 0,
                ctx.mmu.read_f32(record + 48), ctx.mmu.read_f32(record + 52), ctx.mmu.read_f32(record + 56));
            const uint32_t handle = ctx.mmu.read32(record + 180);
            if (!desktop_look_guest_span(handle, 56)) {
                continue;
            }
            uint32_t listener = ctx.mmu.read32(handle);
            for (unsigned i = 0; i < 8 && desktop_look_guest_span(listener, 12); ++i) {
                const uint32_t object = ctx.mmu.read32(listener + 8);
                if (desktop_look_guest_span(object, 8)) {
                    const uint32_t table = ctx.mmu.read32(object);
                    const uint32_t torch = object - 36;
                    if (desktop_look_guest_span(table, 16) && ctx.mmu.read32(table + 12) == 0x80157CA8
                        && object >= 36 && desktop_look_guest_span(torch, 0x2C4) && torch != observed_torch) {
                        std::printf("[DesktopTorch] sample=%u object=%08x active=%u beam=%u timer=%g duration=%g modelAt=%g,%g,%g lightAt=%g,%g,%g\n",
                            count, torch, ctx.mmu.read32(object + 4), ctx.mmu.read8(torch + 323),
                            ctx.mmu.read_f32(torch + 332), ctx.mmu.read_f32(torch + 336),
                            ctx.mmu.read_f32(torch + 416), ctx.mmu.read_f32(torch + 420), ctx.mmu.read_f32(torch + 424),
                            ctx.mmu.read_f32(torch + 544), ctx.mmu.read_f32(torch + 548), ctx.mmu.read_f32(torch + 552));
                        observed_torch = torch;
                    }
                }
                listener = ctx.mmu.read32(listener);
            }
        }
    }

    void turn(nwii::runtime::CPUContext& ctx, const DesktopLookSample& sample,
        uint64_t generation, uint32_t context, float seconds, float requested, float native_yaw) {
        const unsigned reasons = unsigned(std::abs(sample.mouse_x) > 128 || std::abs(sample.mouse_y) > 128)
            | unsigned(seconds > 0.1f) << 1 | unsigned(std::abs(requested) > 35) << 2
            | unsigned(!std::isfinite(native_yaw) || std::abs(native_yaw) > 90) << 3
            | unsigned((sample.mouse_x != 0 || sample.mouse_y != 0)
                && (std::abs(sample.stick_x) > 0.244f || std::abs(sample.stick_y) > 0.244f)) << 4;
        if (reasons == 0 || turn_count >= 64) {
            return;
        }
        const uint32_t now = desktop_look_time_ms();
        if (turn_count != 0 && reasons == turn_reasons && uint32_t(now - turn_time) < 1000) {
            return;
        }
        ++turn_count;
        turn_reasons = reasons;
        turn_time = now;
        std::fprintf(stderr, "[DesktopCameraAnomaly] sample=%u reasons=%u time=%u generation=%llu context=%08x device=%u dt=%g mouse=%g,%g stick=%g,%g requestedDegrees=%g nativeDegrees=%g pc=%08x lr=%08x\n",
            turn_count, reasons, now, static_cast<unsigned long long>(generation), context,
            unsigned(sample.device), seconds, sample.mouse_x, sample.mouse_y, sample.stick_x,
            sample.stick_y, requested, native_yaw, ctx.pc, ctx.lr);
    }

    void interaction(nwii::runtime::CPUContext& ctx, uint32_t object, bool release,
        bool handled, bool focused, uint32_t age, bool blocked) {
        if (grab_count >= 128 || nwii::runtime::Config::get().input_mode != 6
            || ctx.gpr[13] != 0x8052E720 || ctx.gpr[4] != 0x804574F0) {
            return;
        }
        const uint32_t now = desktop_look_time_ms();
        const uint32_t selected = ctx.mmu.read32(0x8052A1FC);
        const uint32_t gui = ctx.mmu.read32(0x80529D20);
        const uint32_t modal = desktop_look_guest_span(gui, 0x9B4) ? ctx.mmu.read32(gui + 0x9B0) : 0xFFFFFFFFu;
        const bool pressed = ctx.mmu.read8(0x804574F0 + 0x58) != 0;
        const uint32_t caller = ctx.gpr[3];
        const uint32_t player = ctx.mmu.read32(0x80491B4C);
        const bool actor_valid = desktop_look_guest_span(caller, 0x5BC);
        const uint32_t table = actor_valid ? ctx.mmu.read32(caller + 0x2C) : 0;
        const uint32_t phase = actor_valid ? ctx.mmu.read32(caller + 0x5B8) : 0xFFFFFFFFu;
        const uint32_t lock = desktop_look_guest_span(player, 0x14FE)
            ? ctx.mmu.read8(player + 0x14FC) : 0xFFFFFFFFu;
        const uint32_t pointer = ctx.mmu.read8(0x804574F0 + 0x30);
        const uint32_t status = unsigned(handled) | unsigned(focused) << 1
            | unsigned(age > 250) << 2 | unsigned(blocked) << 3 | unsigned(pressed) << 4
            | unsigned(release) << 5 | unsigned(pointer != 0) << 6;
        GrabTraceEntry* entry = nullptr;
        for (auto& item : grab_entries) {
            if (item.valid && item.caller == caller && item.release == release) {
                entry = &item;
                break;
            }
        }
        if (entry == nullptr) {
            entry = &grab_entries[grab_entry_next++ % grab_entries.size()];
        }
        if (entry->valid && entry->caller == caller && entry->release == release
            && entry->selected == selected && entry->object == object && entry->status == status
            && entry->modal == modal && entry->phase == phase && entry->lock == lock
            && entry->table == table && (!pressed || uint32_t(now - entry->time) < 1000)) {
            return;
        }
        *entry = {true, release, caller, selected, object, status, modal, phase, lock, table, now};
        ++grab_count;
        std::fprintf(stderr, "[DesktopGrab] sample=%u time=%u caller=%08x object=%08x selected=%08x exclusive=%08x gui=%08x modal=%u release=%u handled=%u A=%u focused=%u age=%u blocked=%u lr=%08x table=%08x phase=%u playerLock=%u pointer=%u xy=%g,%g\n",
            grab_count, now, caller, object, selected, ctx.mmu.read32(0x8052A1F8), gui, modal,
            unsigned(release), unsigned(handled), unsigned(pressed), unsigned(focused), age, unsigned(blocked),
            ctx.lr, table, phase, lock, pointer, ctx.mmu.read_f32(0x804574F0 + 0x28),
            ctx.mmu.read_f32(0x804574F0 + 0x2C));
    }

 private:
    uint32_t owner = 0, count = 0, last_time = 0, last_mode = 0;
    uint32_t turn_count = 0, turn_reasons = 0, turn_time = 0;
    struct GrabTraceEntry {
        bool valid = false, release = false;
        uint32_t caller = 0, selected = 0, object = 0, status = 0, modal = 0;
        uint32_t phase = 0, lock = 0, table = 0, time = 0;
    };
    std::array<GrabTraceEntry, 32> grab_entries{};
    uint32_t grab_count = 0, grab_entry_next = 0;
};

inline DesktopLookTrace& primary_desktop_look_trace() {
    static DesktopLookTrace trace;
    return trace;
}

inline bool desktop_look_trace_enabled() {
    static const bool enabled = [] {
        const char* value = std::getenv("OPENSHSM_TRACE_DESKTOP_LOOK");
        return value != nullptr && value[0] == '1' && value[1] == '\0';
    }();
    return enabled;
}

inline void desktop_look_trace(nwii::runtime::CPUContext& ctx, bool active) {
    if (desktop_look_trace_enabled()) {
        primary_desktop_look_trace().capture(ctx, active, desktop_look_time_ms(), true);
    }
}

class DesktopLookRuntime {
public:
    bool menu_focus(nwii::runtime::CPUContext& ctx) {
        const uint32_t gui = ctx.gpr[30];
        if (nwii::runtime::Config::get().input_mode != 6
            || ctx.gpr[13] != 0x8052E720 || ctx.gpr[3] != 0 || ctx.gpr[4] > 3
            || !latest.focused || !latest.menu_context || latest.device != DesktopInputDevice::Gamepad
            || uint32_t(desktop_look_time_ms() - latest.time_ms) > 250
            || !desktop_look_guest_span(gui, 0x1DAC) || ctx.mmu.read32(0x80529D20) != gui
            || ctx.mmu.read32(0x8052A1FC) != 0) {
            return false;
        }
        const uint32_t begin = ctx.mmu.read32(gui + 0x1DA4);
        const uint32_t end = ctx.mmu.read32(gui + 0x1DA8);
        if (end <= begin || end - begin > 64 * 36 || (end - begin) % 36 != 0
            || !desktop_look_guest_span(begin, end - begin)) {
            return false;
        }
        for (uint32_t record = begin; record < end; record += 36) {
            if (ctx.mmu.read32(record + 4) != 1) {
                continue;
            }
            const uint32_t page = ctx.mmu.read32(record + 0x1C);
            const uint32_t root = ctx.mmu.read32(record + 0x14);
            const uint32_t nodes = ctx.mmu.read32(record + 8);
            const uint32_t nodes_end = ctx.mmu.read32(record + 12);
            if (page < 37 || page > 39 || ctx.mmu.read32(record + 0x18) != 0
                || !desktop_look_guest_span(root, 0x5C) || ctx.mmu.read32(root) != 0x803F4BF0
                || nodes_end <= nodes || nodes_end - nodes > 512 * 4 || (nodes_end - nodes) % 4 != 0
                || !desktop_look_guest_span(nodes, nodes_end - nodes)) {
                return false;
            }
            for (uint32_t entry = nodes; entry < nodes_end; entry += 4) {
                const uint32_t button = ctx.mmu.read32(entry);
                if (!desktop_look_guest_span(button, 0x90) || ctx.mmu.read32(button) != 0x803F44C0
                    || ctx.mmu.read32(button + 0x28) != 0x46CD608C) {
                    continue;
                }
                uint32_t ancestor = button;
                for (unsigned depth = 0; depth < 32; ++depth) {
                    if (!desktop_look_guest_span(ancestor, 0x48) || ctx.mmu.read32(ancestor + 0x44) == 0) {
                        return false;
                    }
                    if (ancestor == root) {
                        ctx.gpr[29] = record;
                        ctx.gpr[31] = button;
                        return true;
                    }
                    ancestor = ctx.mmu.read32(ancestor + 4);
                }
                return false;
            }
            return false;
        }
        return false;
    }

    void inspection_begin(nwii::runtime::CPUContext& ctx) {
        const uint32_t object = ctx.gpr[3];
        if (nwii::runtime::Config::get().input_mode != 6 || ctx.gpr[13] != 0x8052E720
            || (ctx.lr != 0x800E1C18 && ctx.lr != 0x80167250) || !desktop_look_guest_span(object, 0x2E0)
            || !desktop_look_guest_span(ctx.mmu.read32(object + 0xA0), 4)) {
            return;
        }
        if (inspection_owner != object) {
            inspection_owner = object;
            inspection_ready = false;
            inspection_x = inspection_y = 0;
        }
        primary_desktop_look_input().publish_inspection(object);
    }

    void inspection_apply(nwii::runtime::CPUContext& ctx) {
        const uint32_t object = ctx.gpr[30];
        if (nwii::runtime::Config::get().input_mode != 6 || ctx.gpr[13] != 0x8052E720
            || object != inspection_owner || !desktop_look_guest_span(object, 0x2E0)
            || !desktop_look_guest_span(ctx.gpr[1], 0xF8)
            || (ctx.mmu.read32(ctx.gpr[1] + 0xF4) != 0x800E1C18
                && ctx.mmu.read32(ctx.gpr[1] + 0xF4) != 0x80167250)) {
            return;
        }
        if (latest.device != DesktopInputDevice::KeyboardMouse) {
            inspection_ready = false;
            inspection_x = inspection_y = 0;
            return;
        }
        const bool fresh = latest.inspection_context == object && latest.focused && !latest.suspended
            && uint32_t(desktop_look_time_ms() - latest.time_ms) <= 250;
        if (!inspection_ready) {
            if (!fresh) {
                inspection_x = inspection_y = 0;
                return;
            }
            inspection_yaw = ctx.mmu.read_f32(object + 0x168);
            inspection_pitch = ctx.mmu.read_f32(object + 0x16C);
            if (!std::isfinite(inspection_yaw) || !std::isfinite(inspection_pitch)) {
                inspection_x = inspection_y = 0;
                return;
            }
            inspection_ready = true;
        }
        if (fresh) {
            const float configured = nwii::runtime::Config::get().mouse_look_sensitivity;
            const float sensitivity = std::isfinite(configured) ? std::clamp(configured, 0.05f, 5.0f) : 1.0f;
            inspection_yaw = std::remainder(inspection_yaw + inspection_x * 0.005f * sensitivity, 6.283185307179586f);
            inspection_pitch = std::remainder(inspection_pitch + inspection_y * 0.005f * sensitivity,
                6.283185307179586f);
        }
        inspection_x = inspection_y = 0;
        ctx.mmu.write_f32(object + 0x168, inspection_yaw);
        ctx.mmu.write_f32(object + 0x16C, inspection_pitch);
    }

    void inspection_end(nwii::runtime::CPUContext& ctx) {
        if (ctx.gpr[3] == inspection_owner
            && (ctx.lr == 0x800E1BF0 || ctx.lr == 0x80167164 || ctx.lr == 0x801672BC)) {
            primary_desktop_look_input().publish_inspection(0);
            inspection_owner = 0;
            inspection_ready = false;
            inspection_x = inspection_y = 0;
        }
    }

    void validate_context(nwii::runtime::CPUContext& ctx) {
        if (context != 0 && ((context & 0x80000000u)
            ? !pov_allowed(ctx, camera_owner) : (!allowed(ctx, owner)
                || bool(context & 0x40000000u) != (ctx.mmu.read32(owner + 0x1288) == 3)))) {
            reset();
        }
    }

    void pov_begin(nwii::runtime::CPUContext& ctx) {
        const uint32_t camera = ctx.gpr[31];
        if (!pov_allowed(ctx, camera)) {
            if ((context & 0x80000000u) && !pov_allowed(ctx, camera_owner)) {
                reset();
            }
            return;
        }
        const float timer = ctx.mmu.read_f32(camera + 0x12C);
        const float yaw = ctx.mmu.read_f32(camera + 0xC0), pitch = ctx.mmu.read_f32(camera + 0xC4);
        const auto previous = state.pov_angles();
        if (!(context & 0x80000000u) || camera_owner != camera || timer > pov_timer + 0.000001f
            || std::abs(yaw - previous.yaw) > 0.00001f || std::abs(pitch - previous.pitch) > 0.00001f) {
            reset();
            camera_owner = camera;
            context = primary_desktop_look_input().publish(true, desktop_look_time_ms(), true);
            state.enter_pov(context, yaw, pitch);
        } else {
            primary_desktop_look_input().publish(true, desktop_look_time_ms(), true);
        }
        pov_timer = timer;
    }

    bool pov_apply(nwii::runtime::CPUContext& ctx) {
        const uint32_t camera = ctx.gpr[31];
        if (!(context & 0x80000000u) || camera_owner != camera || !pov_allowed(ctx, camera)) {
            return false;
        }
        const auto& config = nwii::runtime::Config::get();
        const float timer = ctx.mmu.read_f32(camera + 0x12C);
        const float blend = ctx.mmu.read8(camera + 0x11A) != 0 ? 1.0f - timer * 4.0f : 1.0f;
        const auto result = state.step_pov(float(ctx.fpr[31]), desktop_look_time_ms(),
            {ctx.mmu.read_f32(camera + 0xA0), ctx.mmu.read_f32(camera + 0xA4),
                ctx.mmu.read_f32(camera + 0x9C), ctx.mmu.read_f32(camera + 0x98),
                ctx.mmu.read_f32(camera + 0xB8), ctx.mmu.read_f32(camera + 0x1A4),
                ctx.mmu.read_f32(camera + 0x1A8), blend * blend},
            {config.mouse_look_sensitivity, config.gamepad_look_sensitivity});
        if (result.valid) {
            ctx.mmu.write_f32(camera + 0xC0, result.yaw);
            ctx.mmu.write_f32(camera + 0xC4, result.pitch);
        }
        ctx.mmu.write_f32(camera + 0x194, 0);
        ctx.mmu.write_f32(camera + 0x198, 0);
        ctx.mmu.write_f32(camera + 0x19C, 0);
        ctx.mmu.write8(camera + 0xD0, 0);
        return true;
    }

    void pov_yaw(nwii::runtime::CPUContext& ctx) {
        const uint32_t camera = ctx.gpr[31];
        if ((context & 0x80000000u) && camera_owner == camera && pov_allowed(ctx, camera)) {
            const float angle = ctx.mmu.read_f32(camera + 0xC0);
            if (std::isfinite(angle)) {
                ctx.mmu.write_f32(camera + 0x1A0, angle);
                ctx.fpr[1] = angle;
            }
        }
    }

    static uint32_t interaction_object(nwii::runtime::CPUContext& ctx) {
        if (nwii::runtime::Config::get().input_mode != 6 || ctx.gpr[13] != 0x8052E720) {
            return 0;
        }
        const uint32_t object = ctx.mmu.read32(0x8052A1FC);
        const uint32_t captured = primary_desktop_look_input().published_interaction_owner();
        if (spline_candidate(ctx, captured) && ctx.mmu.read32(captured + 0x5B8) == 2) {
            return captured;
        }
        if (object == 0) {
            return 0;
        }
        const uint32_t gui = ctx.mmu.read32(0x80529D20);
        const uint32_t exclusive = ctx.mmu.read32(0x8052A1F8);
        if (!desktop_look_guest_span(object, 0x5BC) || !desktop_look_guest_span(gui, 0x9B4)
            || ctx.mmu.read32(gui + 0x9B0) != 0 || (exclusive != 0 && exclusive != object)
            || ctx.mmu.read8(object + 0x4E4) != 1 || ctx.mmu.read8(object + 0x4EC) != 0
            || ctx.mmu.read32(object + 0x5B8) > 2) {
            return 0;
        }
        const uint32_t table = ctx.mmu.read32(object + 0x2C);
        if (!desktop_look_guest_span(table, 0x13C)) {
            return 0;
        }
        const uint32_t begin = ctx.mmu.read32(table + 0x12C);
        const bool shared_begin = begin == 0x80164578
            || (table == 0x803F85A8 && begin == 0x8015A8F8
                && ctx.mmu.read32(0x8015A8F8) == 0x9421FFF0)
            || (table == 0x803FB010 && begin == 0x80171F08
                && ctx.mmu.read32(0x80171F08) == 0x4BFF2670);
        return shared_begin && ctx.mmu.read32(table + 0x130) == 0x80164894 ? object : 0;
    }

    bool interaction_grab(nwii::runtime::CPUContext& ctx) {
        return interaction_button(ctx, false);
    }

    bool interaction_release(nwii::runtime::CPUContext& ctx) {
        return interaction_button(ctx, true);
    }

    void spline_capture(nwii::runtime::CPUContext& ctx) {
        const uint32_t object = ctx.gpr[30];
        if (ctx.gpr[31] == 0x804574F0 && spline_candidate(ctx, object)
            && ctx.mmu.read32(object + 0x5B8) == 2 && latest.focused
            && uint32_t(desktop_look_time_ms() - latest.time_ms) <= 250) {
            primary_desktop_look_input().publish_interaction(object);
        }
    }

    void spline_complete(nwii::runtime::CPUContext& ctx) {
        auto& input = primary_desktop_look_input();
        const uint32_t object = ctx.gpr[30];
        const uint32_t selected = ctx.mmu.read32(0x8052A1FC);
        if (ctx.gpr[13] != 0x8052E720 || (selected != 0 && !button_parent(ctx, selected))) {
            return;
        }
        if (ctx.gpr[31] == 0x804574F0 && spline_candidate(ctx, object)
            && ctx.mmu.read32(object + 0x5B8) == 2 && latest.focused
            && uint32_t(desktop_look_time_ms() - latest.time_ms) <= 250) {
            input.publish_interaction(object);
        } else if (input.published_interaction_owner() == object) {
            input.publish_interaction(0);
        }
    }

    void consume(const DesktopLookSample& sample, uint64_t generation) {
        if (generation > last_generation) {
            last_generation = generation;
            latest = sample;
            if (sample.inspection_context == inspection_owner && inspection_owner != 0
                && sample.focused && !sample.suspended && std::isfinite(sample.mouse_x)
                && std::isfinite(sample.mouse_y)) {
                inspection_x = std::clamp(inspection_x + sample.mouse_x, -4096.0f, 4096.0f);
                inspection_y = std::clamp(inspection_y + sample.mouse_y, -4096.0f, 4096.0f);
            } else {
                inspection_x = inspection_y = 0;
            }
            if (!sample.focused) {
                grab_blocked_until_release = true;
                primary_desktop_look_input().publish_interaction(0);
            }
        }
        state.consume(sample, generation);
    }

    // KPAD inserts a neutral reconnect frame; only raw release samples may rearm Grab.
    void observe_interaction_button(bool focused, bool held) {
        if (!focused) {
            grab_blocked_until_release = true;
        } else if (!held) {
            grab_blocked_until_release = false;
        }
    }

    void begin(nwii::runtime::CPUContext& ctx) {
        desktop_look_trace(ctx, context != 0 && owner == ctx.gpr[3]);
        candidate = ctx.gpr[3];
        selected = false;
        yaw_used = false;
        frame = {};
        axis = 0;
    }

    void player_axis(nwii::runtime::CPUContext& ctx) {
        selected = !(context & 0x80000000u) && ctx.gpr[17] == candidate && ctx.gpr[0] == 0 && allowed(ctx, candidate);
        if (!selected) {
            return;
        }
        if (context && bool(context & 0x40000000u) != (ctx.mmu.read32(candidate + 0x1288) == 3)) {
            reset();
        }
        if (!context || owner != candidate) {
            ctx.fpr[3] = 0;
            return;
        }
        const float seconds = float(ctx.fpr[31]);
        last_seconds = seconds;
        const auto& config = nwii::runtime::Config::get();
        frame = state.step(seconds, desktop_look_time_ms(),
            {config.mouse_look_sensitivity, config.gamepad_look_sensitivity});
        if (frame.valid && std::isfinite(seconds) && seconds > 0) {
            axis = std::clamp(frame.yaw / (3.141592653589793f * std::min(seconds, 0.1f)), -1.0f, 1.0f);
        }
        ctx.fpr[3] = axis;
    }

    void restore_axis(nwii::runtime::CPUContext& ctx) {
        if (selected && context && owner == ctx.gpr[17]) {
            ctx.mmu.write_f32(owner + 0x11B4, axis);
        }
    }

    void yaw_angle(nwii::runtime::CPUContext& ctx) {
        if (selected && context && owner == ctx.gpr[29]) {
            const float degrees = frame.valid && !yaw_used ? frame.yaw * 57.29577951308232f : 0;
            if (!yaw_used) {
                primary_desktop_look_trace().turn(ctx, latest, last_generation, context,
                    last_seconds, degrees, float(ctx.fpr[1]));
            }
            ctx.fpr[1] = degrees;
            yaw_used = true;
        }
    }

    void yaw_follow(nwii::runtime::CPUContext& ctx) {
        if (!selected || !context || !frame.valid || !yaw_used || owner != ctx.gpr[29]
            || !allowed(ctx, owner)) {
            return;
        }
        std::array<float, 3> target{};
        float length = 0;
        for (unsigned i = 0; i < 3; ++i) {
            target[i] = ctx.mmu.read_f32(owner + 0x12AC + i * 4);
            if (!std::isfinite(target[i]) || !std::isfinite(ctx.mmu.read_f32(owner + 0x12A0 + i * 4))) {
                return;
            }
            length += target[i] * target[i];
        }
        if (!std::isfinite(length) || length < 0.9f || length > 1.1f) {
            return;
        }
        for (unsigned i = 0; i < 3; ++i) {
            ctx.mmu.write_f32(owner + 0x12A0 + i * 4, target[i]);
        }
    }

    void camera_snapshot(nwii::runtime::CPUContext& ctx) {
        if ((context & 0x80000000u) && pov_allowed(ctx, camera_owner)) {
            return;
        }
        const uint32_t manager = ctx.gpr[28];
        if (!selected || !allowed(ctx, candidate) || ctx.gpr[3] != candidate + 0xA0
            || !desktop_look_guest_span(manager, 0x250)
            || ctx.mmu.read32(0x80529E44) != manager) {
            reset();
            return;
        }
        snapshot_owner = candidate;
        snapshot_address = manager + 0x1C0;
    }

    void camera_pitch(nwii::runtime::CPUContext& ctx) {
        if ((context & 0x80000000u) && pov_allowed(ctx, camera_owner)) {
            return;
        }
        const uint32_t camera = ctx.gpr[28], profile = ctx.gpr[29], snapshot = ctx.gpr[30];
        if (!selected || !allowed(ctx, candidate) || snapshot_owner != candidate
            || snapshot != snapshot_address
            || !desktop_look_guest_span(snapshot, 0x8C) || !desktop_look_guest_span(camera, 0x98)
            || !desktop_look_guest_span(profile, 0x34)) {
            reset();
            return;
        }
        const uint16_t flags = ctx.mmu.read16(snapshot + 0x80);
        if ((flags & 3u) == 0 || (flags & 0x600u) != 0) {
            reset();
            return;
        }
        const bool photo = ctx.mmu.read32(candidate + 0x1288) == 3;
        if (owner != candidate || camera_owner != camera || !context
            || bool(context & 0x40000000u) != photo) {
            reset();
            snapshot_owner = candidate;
            snapshot_address = snapshot;
            owner = candidate;
            camera_owner = camera;
            const float angle = ctx.mmu.read_f32(camera + 0x88);
            const float limit = ctx.mmu.read_f32(profile + (angle < 0 ? 0x24 : 0x28));
            const float seed = std::isfinite(angle) && std::isfinite(limit) && limit > 0.000001f
                ? angle / limit : float(ctx.fpr[8]);
            context = primary_desktop_look_input().publish(true, desktop_look_time_ms(), false, photo);
            state.enter(context, seed);
            held_pitch = std::isfinite(seed) ? std::clamp(seed, -1.0f, 1.0f) : 0;
            frame = {};
        } else {
            primary_desktop_look_input().publish(true, desktop_look_time_ms(), false, photo);
        }
        if (frame.valid) {
            held_pitch = frame.pitch;
        }
        ctx.fpr[8] = held_pitch;
    }

    void reset() {
        primary_desktop_look_input().publish(false);
        context = owner = camera_owner = 0;
        snapshot_owner = snapshot_address = 0;
        state.enter(0, 0);
        frame = {};
        axis = 0;
        pov_timer = 0;
    }

    void disconnect() {
        latest = {};
        grab_blocked_until_release = true;
        primary_desktop_look_input().publish_interaction(0);
        primary_desktop_look_input().publish_menu(false);
        primary_desktop_look_input().publish_inspection(0);
        inspection_owner = 0;
        inspection_ready = false;
        inspection_x = inspection_y = 0;
        reset();
    }

    void camera_inactive(nwii::runtime::CPUContext& ctx) {
        if ((context & 0x80000000u) && pov_allowed(ctx, camera_owner)) {
            return;
        }
        const uint32_t snapshot = ctx.gpr[30];
        if (!desktop_look_guest_span(snapshot, 0x84) || (ctx.mmu.read16(snapshot + 0x80) & 3u) == 0) {
            reset();
        }
    }

    void flashlight_ray(nwii::runtime::CPUContext& ctx) {
        if (!flashlight_active(ctx, ctx.gpr[29]) || ctx.mmu.read32(0x80491B44) != ctx.gpr[31]) {
            return;
        }
        const uint32_t height = ctx.mmu.read32(0x8052861C);
        if (height >= 1 && height <= 1024) {
            ctx.fpr[31] = 336;
            ctx.fpr[30] = float(height) * 0.5f;
            ctx.mmu.write8(owner + 0x1569, 1);
        }
    }

    void flashlight_gate(nwii::runtime::CPUContext& ctx) {
        if (flashlight_active(ctx, ctx.gpr[27])) {
            ctx.gpr[3] = 0;
        }
    }

    void flashlight_direction(nwii::runtime::CPUContext& ctx) {
        if (!flashlight_active(ctx, ctx.gpr[27]) || !desktop_look_guest_span(ctx.gpr[29], 0x2C4)
            || !desktop_look_guest_span(ctx.gpr[30], 64) || !desktop_look_guest_span(ctx.gpr[1], 0x58)
            || ctx.mmu.read32(ctx.gpr[1] + 0x54) != 0x80156084) {
            return;
        }
        std::array<float, 3> direction{};
        double squared = 0;
        for (unsigned i = 0; i < 3; ++i) {
            direction[i] = ctx.mmu.read_f32(owner + 0x154C + i * 4)
                - ctx.mmu.read_f32(owner + 0x1558 + i * 4);
            if (!std::isfinite(direction[i])) {
                return;
            }
            squared += double(direction[i]) * direction[i];
        }
        if (squared <= 1.0e-12 || squared > std::numeric_limits<float>::max()) {
            return;
        }
        for (unsigned i = 0; i < 3; ++i) {
            ctx.mmu.write_f32(ctx.gpr[1] + 8 + i * 4, direction[i]);
        }
    }

    void flashlight_arm_target(nwii::runtime::CPUContext& ctx) {
        const uint32_t player = ctx.gpr[26];
        if (!flashlight_active(ctx, player) || !desktop_look_guest_span(player, 0x2368)
            || ctx.mmu.read8(player + 0x156A) != 0) {
            return;
        }
        const uint32_t frame = ctx.mmu.read32(player + 0x30);
        if (!desktop_look_guest_span(frame, 0x4C)) {
            return;
        }
        std::array<float, 3> direction{}, target{};
        double squared = 0;
        for (unsigned i = 0; i < 3; ++i) {
            direction[i] = ctx.mmu.read_f32(player + 0x154C + i * 4)
                - ctx.mmu.read_f32(player + 0x1558 + i * 4);
            if (!std::isfinite(direction[i])) {
                return;
            }
            squared += double(direction[i]) * direction[i];
        }
        if (squared <= 1.0e-12 || squared > std::numeric_limits<float>::max()) {
            return;
        }
        const double length = std::sqrt(squared);
        for (unsigned i = 0; i < 3; ++i) {
            const float origin = ctx.mmu.read_f32(frame + 0x40 + i * 4);
            const float axis = float(direction[i] / length);
            target[i] = (origin + (i == 1 ? 1.5f : 0)) + axis * 5.0f;
            if (!std::isfinite(origin) || !std::isfinite(target[i])) {
                return;
            }
        }
        for (uint32_t offset : {0x20C4u, 0x2350u}) {
            if (offset == 0x2350 && ctx.gpr[27] != 0) {
                continue;
            }
            const float weight = ctx.mmu.read_f32(player + offset + 12);
            bool original_target = std::isfinite(weight) && weight > 0 && weight <= 1;
            for (unsigned i = 0; i < 3; ++i) {
                original_target &= ctx.mmu.read32(player + offset + i * 4)
                    == ctx.mmu.read32(player + 0x154C + i * 4);
            }
            if (original_target) {
                for (unsigned i = 0; i < 3; ++i) {
                    ctx.mmu.write_f32(player + offset + i * 4, target[i]);
                }
            }
        }
    }

    bool hide_look_cursor(nwii::runtime::CPUContext& ctx) const {
        return nwii::runtime::Config::get().input_mode == 6 && ctx.gpr[13] == 0x8052E720
            && (ctx.gpr[30] == 0 || ctx.gpr[30] == 7 || ctx.gpr[30] == 10)
            && desktop_look_guest_span(ctx.gpr[28], 0x9C);
    }

private:
    bool pov_allowed(nwii::runtime::CPUContext& ctx, uint32_t camera) const {
        if (nwii::runtime::Config::get().input_mode != 6 || ctx.gpr[13] != 0x8052E720
            || !desktop_look_guest_span(camera, 0x1B8) || ctx.mmu.read32(camera + 0x2C) != 0x803EA8E0
            || ctx.mmu.read8(camera + 0x150) != 0 || ctx.mmu.read8(camera + 0xD2) != 1
            || interaction_object(ctx) != 0) {
            return false;
        }
        const float timer = ctx.mmu.read_f32(camera + 0x12C);
        if (!std::isfinite(timer) || timer < 0 || timer > 0.25f) {
            return false;
        }
        const uint32_t director = ctx.mmu.read32(0x80529E44);
        const uint32_t gui = ctx.mmu.read32(0x80529D20);
        if (gui != 0 && (!desktop_look_guest_span(gui, 0x9B4)
            || ctx.mmu.read32(gui + 0x694) != 0 || ctx.mmu.read32(gui + 0x9B0) != 0)) {
            return false;
        }
        if (!desktop_look_guest_span(director, 0x2A4)) {
            return false;
        }
        const uint32_t override = ctx.mmu.read32(director + 0x2A0);
        uint32_t active = 0;
        if (override != 0) {
            if (!desktop_look_guest_span(override, 4)) {
                return false;
            }
            active = ctx.mmu.read32(override);
        }
        if (active == 0) {
            const uint32_t index = ctx.mmu.read32(director + 8);
            if (index >= (0x2A0 - 0xC0) / 4) {
                return false;
            }
            active = ctx.mmu.read32(director + 0xC0 + index * 4);
        }
        return active == camera;
    }

    bool interaction_button(nwii::runtime::CPUContext& ctx, bool release) {
        uint32_t object = interaction_object(ctx);
        if (object != ctx.gpr[3] && spline_candidate(ctx, ctx.gpr[3])) {
            object = ctx.gpr[3];
        }
        if (object == 0 && nwii::runtime::Config::get().input_mode == 6
            && ctx.gpr[13] == 0x8052E720 && desktop_look_guest_span(ctx.gpr[3], 0x160)
            && ctx.mmu.read32(0x8052A1FC) == ctx.gpr[3]) {
            const uint32_t gui = ctx.mmu.read32(0x80529D20);
            const uint32_t exclusive = ctx.mmu.read32(0x8052A1F8);
            if (desktop_look_guest_span(gui, 0x9B4) && ctx.mmu.read32(gui + 0x9B0) == 0
                && (exclusive == 0 || exclusive == ctx.gpr[3])) {
                object = ctx.gpr[3];
            }
        }
        const uint32_t age = uint32_t(desktop_look_time_ms() - latest.time_ms);
        const bool handled = object != 0 && ctx.gpr[3] == object && ctx.gpr[4] == 0x804574F0;
        if (desktop_look_trace_enabled()) {
            primary_desktop_look_trace().interaction(ctx, object, release, handled,
                latest.focused, age, grab_blocked_until_release);
        }
        if (!handled) {
            return false;
        }
        const bool fresh = latest.focused && age <= 250;
        const bool pressed = ctx.mmu.read8(0x804574F0 + 0x58) != 0;
        const bool held = fresh && pressed;
        ctx.gpr[3] = release ? !held : (held && !grab_blocked_until_release);
        ctx.pc = ctx.lr;
        return true;
    }

    static bool button_parent(nwii::runtime::CPUContext& ctx, uint32_t object) {
        return desktop_look_guest_span(object, 0x5BC)
            && ctx.mmu.read32(object + 0x2C) == 0x803F85A8
            && ctx.mmu.read32(0x803F86D4) == 0x8015A8F8
            && ctx.mmu.read32(0x8015A8F8) == 0x9421FFF0
            && ctx.mmu.read32(0x803F86D8) == 0x80164894
            && ctx.mmu.read8(object + 0x4E4) == 1 && ctx.mmu.read8(object + 0x4EC) == 0
            && ctx.mmu.read32(object + 0x5B8) <= 2;
    }

    static bool spline_candidate(nwii::runtime::CPUContext& ctx, uint32_t object) {
        const uint32_t selected = ctx.mmu.read32(0x8052A1FC);
        const bool nested = selected != 0 && button_parent(ctx, selected);
        if (nwii::runtime::Config::get().input_mode != 6 || ctx.gpr[13] != 0x8052E720
            || (selected != 0 && !nested) || !desktop_look_guest_span(object, 0x604)) {
            return false;
        }
        const uint32_t gui = ctx.mmu.read32(0x80529D20);
        const uint32_t exclusive = ctx.mmu.read32(0x8052A1F8);
        const uint32_t captured = primary_desktop_look_input().published_interaction_owner();
        return desktop_look_guest_span(gui, 0x9B4) && ctx.mmu.read32(gui + 0x9B0) == 0
            && (exclusive == 0 || exclusive == object)
            && (captured == 0 || captured == object || (nested && captured == selected))
            && ctx.mmu.read32(object + 0x2C) == 0x803FB010
            && ctx.mmu.read32(0x803FB13C) == 0x80171F08
            && ctx.mmu.read32(0x80171F08) == 0x4BFF2670
            && ctx.mmu.read32(0x803FB140) == 0x80164894
            && ctx.mmu.read32(0x803FB144) == 0x80164BE0
            && ctx.mmu.read32(0x803FB148) == 0x80171DDC
            && ctx.mmu.read8(object + 0x4E4) == 1 && ctx.mmu.read8(object + 0x4EC) == 1
            && ctx.mmu.read32(object + 0x5B8) <= 2;
    }

    bool flashlight_active(nwii::runtime::CPUContext& ctx, uint32_t player) const {
        return selected && context != 0 && player == owner && player == candidate
            && desktop_look_guest_span(player, 0x156A)
            && ctx.mmu.read32(0x80491B4C) == player && allowed(ctx, player)
            && ctx.mmu.read32(player + 0x1288) <= 1;
    }

    bool allowed(nwii::runtime::CPUContext& ctx, uint32_t player) const {
        if (nwii::runtime::Config::get().input_mode != 6 || ctx.gpr[13] != 0x8052E720
            || !desktop_look_guest_span(player, 0x14FE) || !latest.focused || latest.suspended
            || uint32_t(desktop_look_time_ms() - latest.time_ms) > 250) {
            return false;
        }
        const uint32_t gui = ctx.mmu.read32(0x80529D20);
        if (gui != 0 && (!desktop_look_guest_span(gui, 0x698) || ctx.mmu.read32(gui + 0x694) != 0)) {
            return false;
        }
        const uint32_t controller = ctx.mmu.read32(0x80529160);
        if (!desktop_look_guest_span(controller, 0x513A) || ctx.mmu.read8(controller + 0x5139) != 0) {
            return false;
        }
        if (ctx.mmu.read8(player + 0x14FD) != 0 || interaction_object(ctx) != 0) {
            return false;
        }
        const float restricted = ctx.mmu.read_f32(player + 0x138C);
        const uint32_t mode = ctx.mmu.read32(player + 0x1288);
        return (mode <= 1 || mode == 3)
            && (ctx.mmu.read16(player + 0x120) & 0x600u) == 0
            && ctx.mmu.read8(player + 0x608) == 0
            && int32_t(ctx.mmu.read32(player + 0x1388)) <= 0
            && std::isfinite(restricted) && restricted <= 0;
    }

    DesktopLookState state;
    DesktopLookSample latest{};
    DesktopLookDelta frame{};
    uint64_t last_generation = 0;
    uint32_t candidate = 0, owner = 0, camera_owner = 0, context = 0;
    uint32_t inspection_owner = 0;
    bool inspection_ready = false;
    float inspection_x = 0, inspection_y = 0, inspection_yaw = 0, inspection_pitch = 0;
    uint32_t snapshot_owner = 0, snapshot_address = 0;
    float axis = 0, held_pitch = 0, last_seconds = 0;
    float pov_timer = 0;
    bool selected = false, yaw_used = false, grab_blocked_until_release = false;
};

inline DesktopLookRuntime& primary_desktop_look_runtime() {
    static DesktopLookRuntime runtime;
    return runtime;
}

inline bool desktop_twist_current_sample(nwii::runtime::CPUContext& ctx) {
    constexpr uint32_t sample = 0x804579C8;
    const uint32_t object = ctx.gpr[30];
    if (nwii::runtime::Config::get().input_mode != 6 || ctx.gpr[13] != 0x8052E720
        || !desktop_look_guest_span(object, 0x5F4) || !desktop_look_guest_span(ctx.gpr[1], 0x20)
        || ctx.mmu.read32(object + 0x2C) != 0x803FB7D0
        || ctx.mmu.read32(0x8052A1FC) != object || ctx.mmu.read8(object + 0x4E4) != 1
        || ctx.mmu.read8(object + 0x4EC) != 0 || ctx.mmu.read32(object + 0x5B8) != 2
        || ctx.mmu.read8(0x804579C0) != 1 || ctx.mmu.read8(sample + 0x5C) != 1
        || ctx.mmu.read8(sample + 0x5D) != 0) {
        return false;
    }
    const uint32_t controller = ctx.mmu.read32(ctx.gpr[13] - 0x55C0);
    if (!desktop_look_guest_span(controller, 0x513A) || ctx.mmu.read32(controller) != 0x803DFAF0
        || ctx.mmu.read8(controller + 0x5139) != 1) {
        return false;
    }
    const auto saved_r3 = ctx.gpr[3], saved_r4 = ctx.gpr[4], saved_pc = ctx.pc;
    ctx.gpr[3] = object;
    ctx.gpr[4] = 0x804574F0;
    const bool handled = primary_desktop_look_runtime().interaction_grab(ctx);
    const bool held = ctx.gpr[3] != 0;
    ctx.gpr[3] = saved_r3;
    ctx.gpr[4] = saved_r4;
    ctx.pc = saved_pc;
    if (!handled || !held) {
        return false;
    }
    const float x = ctx.mmu.read_f32(sample + 0x38), y = ctx.mmu.read_f32(sample + 0x34);
    const float length_squared = x * x + y * y;
    if (!std::isfinite(x) || !std::isfinite(y) || length_squared < 0.25f || length_squared > 4.0f) {
        return false;
    }
    ctx.mmu.write_f32(ctx.gpr[1] + 0x10, x);
    ctx.mmu.write_f32(ctx.gpr[1] + 0x14, y);
    return true;
}

}
