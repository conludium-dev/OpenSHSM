#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>

namespace openshsm::experiment {

class DesktopRoll {
public:
    std::array<float, 3> update(uint32_t ticks, bool focused, bool left, bool right,
            bool center, int mouse_pixels) {
        constexpr double pi = 3.14159265358979323846;
        const uint32_t elapsed = ticks - previous_ticks;
        const double seconds = initialized && was_focused && focused
            ? std::min(elapsed, uint32_t(100)) * 0.001 : 0.0;
        previous_ticks = ticks;
        initialized = true;
        was_focused = focused;
        if (!focused || center) {
            angle = 0.0;
            release_gesture();
        } else {
            const double mouse_delta = mouse_pixels * pi / 720.0;
            const double maximum_delta = 40.0 * pi / 180.0 * seconds;
            const double mouse_turn = twist_context()
                ? std::clamp(mouse_delta, -maximum_delta, maximum_delta) : mouse_delta;
            angle = std::remainder(angle + (int(right) - int(left)) * pi * 0.5 * seconds
                + mouse_turn, 2.0 * pi);
        }
        return {float(-std::sin(angle)), float(-std::cos(angle)), 0.0f};
    }

    void publish_twist_context(bool enabled, uint32_t controller = 0) {
        constexpr uint64_t mask = (uint64_t(1) << 33) - 1;
        const uint64_t desired = (uint64_t(controller) << 1) | unsigned(enabled);
        uint64_t previous = context.load(std::memory_order_relaxed);
        while ((previous & mask) != desired) {
            const uint64_t next = ((previous + (uint64_t(1) << 33)) & ~mask) | desired;
            if (context.compare_exchange_weak(previous, next, std::memory_order_release,
                    std::memory_order_relaxed)) {
                break;
            }
        }
    }

    void release_gesture() {
        analog_initialized = false;
        analog_grabbed = false;
        clear_circle();
    }

    bool twist_context() const {
        return (context.load(std::memory_order_acquire) & 1u) != 0;
    }

    std::array<float, 3> analog(uint32_t ticks, bool focused, bool grabbed, float x, float y) {
        constexpr double pi = 3.14159265358979323846;
        const uint64_t token = context.load(std::memory_order_acquire);
        const bool active = focused && grabbed && (token & 1u) && std::isfinite(x) && std::isfinite(y)
            && std::abs(x) <= 1.0f && std::abs(y) <= 1.0f;
        const bool continuing = analog_initialized && analog_grabbed && active && token == analog_context;
        const double seconds = continuing
            ? std::min(ticks - analog_ticks, uint32_t(100)) * 0.001 : 0.0;
        analog_ticks = ticks;
        analog_initialized = true;
        analog_grabbed = active;
        analog_context = token;
        if (!focused) {
            angle = 0.0;
        }
        if (!continuing) {
            clear_circle();
        }
        if (!active || std::max(std::abs(x), std::abs(y)) <= 0.625f) {
            clear_circle();
            return {float(-std::sin(angle)), float(-std::cos(angle)), 0.0f};
        }
        const double length = std::hypot(double(x), double(y));
        const double current_x = x / length, current_y = y / length;
        if (circle_ready) {
            const double dot = std::clamp(circle_x * current_x + circle_y * current_y, -1.0, 1.0);
            const double delta = std::acos(dot);
            if (delta > 100.0 * pi / 180.0) {
                clear_circle();
                return {float(-std::sin(angle)), float(-std::cos(angle)), 0.0f};
            }
            if (delta <= 4.0 * pi / 180.0) {
                return {float(-std::sin(angle)), float(-std::cos(angle)), 0.0f};
            }
            const double cross = circle_x * current_y - circle_y * current_x;
            const int direction = cross < 0 ? -1 : 1;
            circle_accumulated += delta;
            if (circle_accumulated > 36.0 * pi / 180.0) {
                angle = std::remainder(angle + direction * pi / 6.0 * seconds, 2.0 * pi);
            } else if (circle_direction && circle_direction != direction) {
                clear_circle();
                return {float(-std::sin(angle)), float(-std::cos(angle)), 0.0f};
            } else {
                circle_direction = direction;
            }
        }
        circle_x = current_x;
        circle_y = current_y;
        circle_ready = true;
        return {float(-std::sin(angle)), float(-std::cos(angle)), 0.0f};
    }

private:
    void clear_circle() {
        circle_ready = false;
        circle_accumulated = 0.0;
        circle_direction = 0;
    }

    std::atomic<uint64_t> context{0};
    double angle = 0.0;
    uint32_t previous_ticks = 0;
    bool initialized = false;
    bool was_focused = false;
    uint32_t analog_ticks = 0;
    bool analog_initialized = false;
    bool analog_grabbed = false;
    uint64_t analog_context = 0;
    bool circle_ready = false;
    double circle_x = 0.0, circle_y = 0.0, circle_accumulated = 0.0;
    int circle_direction = 0;
};

inline DesktopRoll& primary_desktop_roll() {
    static DesktopRoll roll;
    return roll;
}

}
