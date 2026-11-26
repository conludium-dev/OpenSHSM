#pragma once
#include <cstdint>

namespace stock_movie_capture_gate {

struct Gate {
    uint64_t delay_us = 0;
    uint64_t first_us = 0;
    bool started = false;
    bool valid = true;

    explicit Gate(const char* text) {
        if (!text) {
            return;
        }
        if (!*text) {
            valid = false;
            return;
        }
        uint64_t value = 0;
        for (const char* digit = text; *digit; ++digit) {
            if (*digit < '0' || *digit > '9' || value > 180000) {
                valid = false;
                return;
            }
            value = value * 10 + uint64_t(*digit - '0');
        }
        valid = value <= 180000;
        delay_us = valid ? value * 1000 : 0;
    }

    bool accept(uint64_t now_us) {
        if (!valid) {
            return false;
        }
        if (!delay_us) {
            return true;
        }
        if (!started) {
            first_us = now_us;
            started = true;
        }
        return now_us >= first_us && now_us - first_us >= delay_us;
    }
};

}
