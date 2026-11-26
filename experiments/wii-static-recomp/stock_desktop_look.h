#pragma once
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>

namespace openshsm::experiment {

enum class DesktopInputDevice : uint8_t { Unknown, KeyboardMouse, Gamepad };

struct DesktopLookSample {
    uint32_t context = 0;
    uint32_t time_ms = 0;
    float mouse_x = 0, mouse_y = 0;
    float stick_x = 0, stick_y = 0;
    bool focused = false;
    bool suspended = false;
    uint32_t interaction_context = 0;
    uint32_t inspection_context = 0;
    uint8_t qte_buttons = 0;
    DesktopInputDevice device = DesktopInputDevice::Unknown;
    int32_t qte_controller = -1;
    uint32_t qte_context = 0;
    bool menu_context = false;
};

inline uint32_t desktop_look_time_ms() {
    return uint32_t(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}

class DesktopLookInput {
public:
    void publish_inspection(uint32_t object, uint32_t now = desktop_look_time_ms()) {
        inspection_permission.store(object == 0 ? 0 : uint64_t(now) << 32 | object, std::memory_order_release);
    }

    void publish_menu(bool enabled, uint32_t now = desktop_look_time_ms()) {
        menu_permission.store(enabled ? uint64_t(now) << 32 | 1 : 0, std::memory_order_release);
    }

    void publish_qte(uint32_t context, uint32_t now = desktop_look_time_ms()) {
        qte_permission.store(context == 0 ? 0 : uint64_t(now) << 32 | context, std::memory_order_release);
    }

    uint32_t publish_interaction(uint32_t object, uint32_t now = desktop_look_time_ms()) {
        if (object == 0) {
            interaction_owner = 0;
            interaction_permission.store(0, std::memory_order_release);
            return 0;
        }
        if (object != interaction_owner) {
            interaction_owner = object;
            if (++interaction_sequence == 0) {
                ++interaction_sequence;
            }
        }
        interaction_permission.store(uint64_t(now) << 32 | interaction_sequence, std::memory_order_release);
        return interaction_sequence;
    }

    uint32_t published_interaction_owner(uint32_t now = desktop_look_time_ms()) const {
        const uint64_t value = interaction_permission.load(std::memory_order_acquire);
        return uint32_t(value) != 0 && uint32_t(now - uint32_t(value >> 32)) <= 250
            ? interaction_owner : 0;
    }

    // CPU publishes permission; the host collects into the existing InputManager snapshot.
    uint32_t publish(bool enabled, uint32_t now = desktop_look_time_ms(), bool pov = false, bool photo = false) {
        const uint64_t previous = permission.load(std::memory_order_relaxed);
        if (!enabled || (pov && photo)) {
            permission.store(0, std::memory_order_release);
            return 0;
        }
        const uint32_t kind = pov ? 0x80000000u : photo ? 0x40000000u : 0;
        uint32_t context = uint32_t(previous);
        if (!context || (context & 0xC0000000u) != kind) {
            sequence = (sequence + 1) & 0x3FFFFFFFu;
            context = sequence;
            if (!context) {
                context = ++sequence;
            }
            context |= kind;
        }
        permission.store(uint64_t(now) << 32 | context, std::memory_order_release);
        return context;
    }

    void begin(uint32_t now = desktop_look_time_ms()) {
        const uint64_t value = permission.load(std::memory_order_acquire);
        frame = {};
        frame.time_ms = now;
        frame.device = active_device;
        if (uint32_t(now - uint32_t(value >> 32)) <= 250) {
            frame.context = uint32_t(value);
        }
        const uint64_t interaction = interaction_permission.load(std::memory_order_acquire);
        if (uint32_t(now - uint32_t(interaction >> 32)) <= 250) {
            frame.interaction_context = uint32_t(interaction);
        }
        const uint64_t menu = menu_permission.load(std::memory_order_acquire);
        const uint64_t inspection = inspection_permission.load(std::memory_order_acquire);
        if (uint32_t(now - uint32_t(inspection >> 32)) <= 250) {
            frame.inspection_context = uint32_t(inspection);
        }
        frame.menu_context = uint32_t(menu) != 0 && uint32_t(now - uint32_t(menu >> 32)) <= 250;
        const uint64_t qte = qte_permission.load(std::memory_order_acquire);
        if (uint32_t(now - uint32_t(qte >> 32)) <= 250) {
            frame.qte_context = uint32_t(qte);
        }
    }

    void mouse(float x, float y, bool focused, bool suspended) {
        frame.focused = focused;
        frame.suspended |= suspended;
        if (focused && !suspended && std::isfinite(x) && std::isfinite(y)) {
            if (x != 0 || y != 0) {
                activity(DesktopInputDevice::KeyboardMouse);
            }
            frame.mouse_x += std::clamp(x, -4096.0f, 4096.0f);
            frame.mouse_y += std::clamp(y, -4096.0f, 4096.0f);
        }
    }

    void stick(float x, float y, bool focused, bool suspended) {
        frame.focused = focused;
        frame.suspended |= suspended;
        if (focused && !suspended && std::isfinite(x) && std::isfinite(y)) {
            if (std::max(std::abs(x), std::abs(y)) > 0.2f) {
                activity(DesktopInputDevice::Gamepad);
            }
            frame.stick_x = std::clamp(x, -1.0f, 1.0f);
            frame.stick_y = std::clamp(y, -1.0f, 1.0f);
        }
    }

    bool world() const {
        return direct() && !(frame.context & 0xC0000000u);
    }

    bool pov() const {
        return direct() && (frame.context & 0x80000000u);
    }

    bool photo() const {
        return direct() && (frame.context & 0xC0000000u) == 0x40000000u;
    }

    bool direct() const {
        return frame.context != 0 && frame.interaction_context == 0;
    }

    void buttons(uint8_t mask, bool focused, int32_t controller = -1) {
        if (focused && controller >= -1 && (mask & 0xF0) == 0) {
            frame.qte_buttons |= mask;
            if (mask != 0) {
                activity(controller >= 0 ? DesktopInputDevice::Gamepad : DesktopInputDevice::KeyboardMouse);
            }
            if (controller >= 0) {
                frame.qte_controller = controller;
            }
        }
    }

    void activity(DesktopInputDevice device) {
        if (device == DesktopInputDevice::KeyboardMouse || device == DesktopInputDevice::Gamepad) {
            active_device = frame.device = device;
        }
    }

    bool interaction() const {
        return frame.interaction_context != 0;
    }

    DesktopLookSample sample() const {
        return frame;
    }

private:
    static_assert(std::atomic<uint64_t>::is_always_lock_free);
    std::atomic<uint64_t> permission{0};
    std::atomic<uint64_t> interaction_permission{0};
    std::atomic<uint64_t> qte_permission{0};
    std::atomic<uint64_t> menu_permission{0};
    std::atomic<uint64_t> inspection_permission{0};
    uint32_t interaction_owner = 0, interaction_sequence = 0;
    uint32_t sequence = 0;
    DesktopLookSample frame{};
    DesktopInputDevice active_device = DesktopInputDevice::Unknown;
};

inline DesktopLookInput& primary_desktop_look_input() {
    static DesktopLookInput input;
    return input;
}

struct DesktopLookDelta {
    float yaw = 0;
    float pitch = 0;
    bool valid = false;
};

struct DesktopLookSettings {
    float mouse_sensitivity = 1;
    float gamepad_sensitivity = 1;
};

struct DesktopPovSettings {
    float yaw_min = 0, yaw_max = 0, pitch_min = 0, pitch_max = 0;
    float speed = 0, yaw_acceleration = 0, pitch_acceleration = 0;
    float input_weight = 1;
};

class DesktopLookState {
public:
    DesktopLookDelta pov_angles() const {
        return {pov_yaw, pov_pitch, active_context != 0};
    }

    void enter_pov(uint32_t context, float yaw, float vertical) {
        enter(context, 0);
        pov_yaw = std::isfinite(yaw) ? yaw : 0;
        pov_pitch = std::isfinite(vertical) ? vertical : 0;
        yaw_velocity = pitch_velocity = 0;
    }

    void enter(uint32_t context, float seed_pitch) {
        if (context != active_context) {
            active_context = context;
            pitch = std::isfinite(seed_pitch) ? std::clamp(seed_pitch, -1.0f, 1.0f) : 0;
            latest = {};
            mouse_x = mouse_y = 0;
            mouse_seconds = 0;
            yaw_velocity = pitch_velocity = 0;
        }
    }

    void consume(const DesktopLookSample& sample, uint64_t generation) {
        if (generation <= last_generation) {
            return;
        }
        last_generation = generation;
        if (!active_context || sample.context != active_context || !sample.focused || sample.suspended
            || !std::isfinite(sample.mouse_x) || !std::isfinite(sample.mouse_y)
            || !std::isfinite(sample.stick_x) || !std::isfinite(sample.stick_y)) {
            latest = {};
            mouse_x = mouse_y = 0;
            mouse_seconds = 0;
            yaw_velocity = pitch_velocity = 0;
            return;
        }
        latest = sample;
        mouse_x = std::clamp(mouse_x + sample.mouse_x, -4096.0f, 4096.0f);
        mouse_y = std::clamp(mouse_y + sample.mouse_y, -4096.0f, 4096.0f);
    }

    DesktopLookDelta step(float seconds, uint32_t now = desktop_look_time_ms(),
        DesktopLookSettings settings = {}) {
        if (!active_context || latest.context != active_context || !std::isfinite(seconds)
            || seconds <= 0 || uint32_t(now - latest.time_ms) > 250) {
            mouse_x = mouse_y = 0;
            mouse_seconds = 0;
            return {0, pitch, false};
        }
        const float dt = std::min(seconds, 0.1f);
        const float mouse = sensitivity(settings.mouse_sensitivity);
        const float gamepad = sensitivity(settings.gamepad_sensitivity);
        const float dx = mouse_x, dy = mouse_y;
        mouse_x = mouse_y = mouse_seconds = 0;
        const float yaw = -dx * 0.0025f * mouse
            - shaped(latest.stick_x) * 3.141592653589793f * dt * gamepad;
        pitch = std::clamp(pitch + dy * 0.002f * mouse
            + shaped(latest.stick_y) * 2.0f * dt * gamepad, -1.0f, 1.0f);
        return {yaw, pitch, true};
    }

    DesktopLookDelta step_pov(float seconds, uint32_t now, DesktopPovSettings profile,
        DesktopLookSettings settings = {}) {
        if (!active_context || latest.context != active_context || !std::isfinite(seconds)
            || seconds <= 0 || uint32_t(now - latest.time_ms) > 250) {
            mouse_x = mouse_y = mouse_seconds = 0;
            yaw_velocity = pitch_velocity = 0;
            return {pov_yaw, pov_pitch, false};
        }
        const float values[] = {profile.yaw_min, profile.yaw_max, profile.pitch_min, profile.pitch_max,
            profile.speed, profile.yaw_acceleration, profile.pitch_acceleration};
        for (float value : values) {
            if (!std::isfinite(value) || value < 0 || value > 360) {
                mouse_x = mouse_y = mouse_seconds = 0;
                yaw_velocity = pitch_velocity = 0;
                return {pov_yaw, pov_pitch, false};
            }
        }
        if (!std::isfinite(profile.input_weight) || profile.input_weight < 0 || profile.input_weight > 1) {
            mouse_x = mouse_y = mouse_seconds = 0;
            yaw_velocity = pitch_velocity = 0;
            return {pov_yaw, pov_pitch, false};
        }
        const float dt = std::min(seconds, 0.1f);
        const float dx = mouse_x, dy = mouse_y;
        mouse_x = mouse_y = mouse_seconds = 0;
        const auto advance = [dt, weight = profile.input_weight](float current, float target, float rate) {
            target = std::clamp(target, -1.0f, 1.0f);
            target = std::abs(target) < 0.3f ? 0 : target * weight;
            const float amount = rate * dt;
            return current + std::clamp(target - current, -amount, amount);
        };
        yaw_velocity = advance(yaw_velocity, -latest.stick_x, profile.yaw_acceleration);
        pitch_velocity = advance(pitch_velocity, -latest.stick_y, profile.pitch_acceleration);
        const float mouse = sensitivity(settings.mouse_sensitivity) * profile.input_weight;
        const float speed = profile.speed * sensitivity(settings.gamepad_sensitivity);
        pov_yaw = std::clamp(pov_yaw + yaw_velocity * speed * dt - dx * 0.14323945f * mouse,
            -profile.yaw_min, profile.yaw_max);
        pov_pitch = std::clamp(pov_pitch + pitch_velocity * speed * dt - dy * 0.14323945f * mouse,
            -profile.pitch_min, profile.pitch_max);
        return {pov_yaw, pov_pitch, true};
    }

private:
    static float sensitivity(float value) {
        return std::isfinite(value) && value >= 0.05f && value <= 5.0f ? value : 1.0f;
    }

    static float shaped(float value) {
        const float axis = std::clamp((std::abs(value) - 0.18f) / 0.82f, 0.0f, 1.0f);
        return std::copysign(axis * axis, value);
    }

    uint32_t active_context = 0;
    uint64_t last_generation = 0;
    DesktopLookSample latest{};
    float mouse_x = 0, mouse_y = 0, mouse_seconds = 0, pitch = 0;
    float pov_yaw = 0, pov_pitch = 0, yaw_velocity = 0, pitch_velocity = 0;
};

}
