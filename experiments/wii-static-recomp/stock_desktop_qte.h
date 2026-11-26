#pragma once
#include "stock_desktop_look.h"
#include <cstdint>
#include <atomic>

namespace openshsm::experiment {

struct DesktopQTEPrompt {
    uint32_t context = 0;
    unsigned target = 4;
    bool blocked = false;
    DesktopInputDevice device = DesktopInputDevice::Unknown;
};

class DesktopQTEPromptChannel {
public:
    static constexpr uint32_t max_context = 0x07FFFFFF;

    void publish(uint32_t context, unsigned target, bool blocked, uint32_t now,
        DesktopInputDevice device = DesktopInputDevice::Unknown) {
        offer.store(context == 0 || context > max_context || target >= 4
            || device > DesktopInputDevice::Gamepad ? 0 : uint64_t(context) << 37
            | uint64_t(now) << 5 | uint64_t(device) << 3 | unsigned(blocked) << 2 | target,
            std::memory_order_release);
    }

    DesktopQTEPrompt read(uint32_t now) const {
        const uint64_t value = offer.load(std::memory_order_acquire);
        if (uint32_t(value >> 37) == 0 || uint32_t(now - uint32_t(value >> 5)) > 250) {
            return {};
        }
        return {uint32_t(value >> 37), unsigned(value & 3), (value & 4) != 0,
            DesktopInputDevice((value >> 3) & 3)};
    }

    void presented(uint32_t context, uint32_t now) {
        visible.store(context == 0 ? 0 : uint64_t(now) << 32 | context, std::memory_order_release);
    }

    bool shown(uint32_t context, uint32_t now) const {
        const uint64_t value = visible.load(std::memory_order_acquire);
        return context != 0 && uint32_t(value) == context && uint32_t(now - uint32_t(value >> 32)) <= 250;
    }

private:
    std::atomic<uint64_t> offer{0}, visible{0};
};

inline DesktopQTEPromptChannel& primary_desktop_qte_prompt() {
    static DesktopQTEPromptChannel channel;
    return channel;
}

class DesktopQTEState {
public:
    void enter(uint64_t context, unsigned button) {
        if (context == active_context && button == target) {
            return;
        }
        active_context = button < 4 ? context : 0;
        target = button;
        edges = 0;
        focused = false;
        blocked = false;
        accepted = false;
        issued = false;
    }

    void consume(uint8_t buttons, bool focus, uint32_t now, uint64_t generation) {
        if (generation <= last_generation) {
            return;
        }
        last_generation = generation;
        if (!active_context || !focus || (buttons & 0xF0) != 0) {
            edges = 0;
            focused = false;
            issued = false;
            return;
        }
        if (!focused || uint32_t(now - last_time) > 250) {
            previous = buttons;
            edges = 0;
        } else {
            edges |= buttons & ~previous;
            previous = buttons;
        }
        last_time = now;
        focused = true;
    }

    void reset_input() {
        previous = edges = 0;
        focused = issued = false;
    }

    int request(uint32_t now) {
        issued = false;
        const uint8_t pressed = edges;
        edges = 0;
        if (!active_context || !focused || uint32_t(now - last_time) > 250) {
            focused = false;
            return -1;
        }
        if (blocked && uint32_t(now - blocked_at) < 5000) {
            return -1;
        }
        blocked = false;
        if (accepted || pressed == 0) {
            return -1;
        }
        const uint8_t correct = uint8_t(1u << target);
        if ((pressed & ~correct) != 0) {
            blocked_at = now;
            blocked = true;
            return -1;
        }
        issued = true;
        return int(target);
    }

    void acknowledge() {
        accepted |= active_context != 0 && issued;
        issued = false;
        edges = 0;
    }

    void rearm() {
        accepted = false;
    }

    uint32_t remaining_ms(uint32_t now) const {
        const uint32_t elapsed = uint32_t(now - blocked_at);
        return blocked && elapsed < 5000 ? 5000 - elapsed : 0;
    }

private:
    uint64_t active_context = 0, last_generation = 0;
    unsigned target = 4;
    uint32_t last_time = 0, blocked_at = 0;
    uint8_t previous = 0, edges = 0;
    bool focused = false, blocked = false, accepted = false, issued = false;
};

}
