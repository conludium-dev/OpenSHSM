#include "stock_dsp_replies.h"
#include "Core/HW/DSPHLE/MailHandler.h"
#include "Core/HW/DSP.h"
#include <iostream>

using openshsm::experiment::DspMailReplies;

static void require(bool value) {
    if (!value) {
        throw std::runtime_error("DSP reply reference mismatch");
    }
}

int main() {
    DSP::DSPManager dsp;
    DSP::HLE::CMailHandler reference(dsp);
    DspMailReplies candidate;
    std::vector<int> signals;
    const auto signal = [&](int delay) noexcept { signals.push_back(delay); };
    reference.PushMail(0xdcd10004, true, 0);
    reference.PushMail(0xdcd10002, true, 2500);
    candidate.push(0xdcd10004, true, 0, signal);
    candidate.push(0xdcd10002, true, 2500, signal);
    require(candidate.read_high() == reference.ReadDSPMailboxHigh());
    require(candidate.read_low(signal) == reference.ReadDSPMailboxLow());
    require(candidate.read_high() == reference.ReadDSPMailboxHigh());
    require(candidate.read_low(signal) == reference.ReadDSPMailboxLow());
    require(candidate.read_high() == reference.ReadDSPMailboxHigh());
    require(signals == dsp.interrupts && signals == std::vector<int>{0, 0});
    unsigned pending = 0;
    uint32_t random = 0x5348534d;
    for (unsigned iteration = 0; iteration < 131072; ++iteration) {
        random ^= random << 13;
        random ^= random >> 17;
        random ^= random << 5;
        const unsigned action = random % 8;
        if (action < 3 && pending < 31) {
            const uint32_t mail = random ^ 0xdcd10000;
            const bool interrupt = (random & 0x100) != 0;
            const int delay = int(random & 4095);
            reference.PushMail(mail, interrupt, delay);
            candidate.push(mail, interrupt, delay, signal);
            ++pending;
        } else if (action == 3) {
            require(candidate.read_high() == reference.ReadDSPMailboxHigh());
        } else if (action == 4) {
            candidate.set_halted(false);
            reference.SetHalted(false);
            require(candidate.read_low(signal) == reference.ReadDSPMailboxLow());
            pending -= pending != 0;
        } else if (action == 5) {
            candidate.set_halted(true);
            reference.SetHalted(true);
            require(candidate.read_low(signal) == reference.ReadDSPMailboxLow());
            require(candidate.read_high() == reference.ReadDSPMailboxHigh());
        } else if (action == 6) {
            candidate.clear_pending();
            reference.ClearPending();
            pending = 0;
        }
        require(candidate.has_pending() == reference.HasPending() && signals == dsp.interrupts);
    }
    candidate.clear_pending();
    candidate.set_halted(false);
    for (unsigned index = 0; index < 32; ++index) {
        candidate.push(0xdcd10000 | index, false, 0, signal);
    }
    const auto before = signals;
    unsigned refused = 0;
    for (int delay : {0, -1}) {
        try {
            candidate.push(0xffffffff, true, delay, signal);
        } catch (const std::runtime_error&) {
            ++refused;
        }
    }
    require(refused == 2 && signals == before);
    for (unsigned index = 0; index < 32; ++index) {
        require(candidate.read_high() == 0xdcd1 && candidate.read_low(signal) == index);
    }
    require(!candidate.has_pending() && signals == before);
    std::cout << "DSP_REPLIES_REFERENCE_PASS 131072 operations;SYNC4-before-YIELD2;2 guarded refusals\n";
}
