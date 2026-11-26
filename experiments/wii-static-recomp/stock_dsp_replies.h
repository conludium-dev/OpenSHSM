// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <array>
#include <cstdint>
#include <stdexcept>

namespace openshsm::experiment {

class DspMailReplies {
public:
    template<class Signal>
    void push(uint32_t mail, bool interrupt, int delay, Signal&& signal) {
        if (count == pending.size() || delay < 0) {
            throw std::runtime_error("Invalid or full DSP reply queue");
        }
        if (interrupt) {
            if (!count) {
                signal(delay);
            } else {
                pending[head].next_interrupt = true;
            }
        }
        pending[(head + count) % pending.size()] = {mail, false};
        ++count;
    }

    uint16_t read_high() {
        if (!halted && count) {
            last = pending[head].mail;
        }
        return uint16_t(last >> 16);
    }

    template<class Signal>
    uint16_t read_low(Signal&& signal) {
        if (!halted && count) {
            last = pending[head].mail;
            const bool interrupt = pending[head].next_interrupt;
            head = (head + 1) % pending.size();
            --count;
            if (interrupt) {
                signal(0);
            }
        }
        last &= 0x7fffffffu;
        return uint16_t(last);
    }

    void clear_pending() {
        count = 0;
        head = 0;
    }

    void set_halted(bool value) {
        halted = value;
    }

    bool has_pending() const {
        return count != 0;
    }

private:
    struct Reply {
        uint32_t mail = 0;
        bool next_interrupt = false;
    };
    std::array<Reply, 32> pending{};
    unsigned head = 0, count = 0;
    uint32_t last = 0;
    bool halted = false;
};

}
