#include "dsp_startup_frontend.h"
#include "loader-bat-seed.h"
#include "loader/loader.h"
#include <iostream>

namespace nwii::runtime {
CPUContext* g_ctx_ptr = nullptr;
MMU* g_mmu = nullptr;
uint16_t HW_Reg_Read16(uint32_t) { throw std::runtime_error("Audio playback MMIO outside startup contract"); }
}

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc != 2) { return 2; }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) { return 3; }
    SeededBatContext context;
    for (const auto& section : executable.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
    }
    context.msr = 0x2032;
    hw::register_pi(MMIODispatcher::get());
    hw::register_dsp(MMIODispatcher::get());
    const std::array<std::array<uint32_t, 3>, 17> commands{{
        {0xcc005012, 0x43, 2}, {0xcc00500a, 0x8ac, 2}, {0xcc00500a, 0x805, 2}, {0xcc005000, 0, 2},
        {0xcc005020, 0x01000000, 4}, {0xcc005024, 0, 4}, {0xcc005028, 32, 4}, {0xcc00500a, 0x824, 2},
        {0xcc005020, 0x01000000, 4}, {0xcc005024, 0, 4}, {0xcc005028, 32, 4}, {0xcc00500a, 0x824, 2},
        {0xcc00500a, 4, 2}, {0xcc00500a, 0, 2}, {0xcc00500a, 4, 2}, {0xcc00500a, 0x8ac, 2}, {0xcc00500a, 0x805, 2}
    }};
    for (unsigned mode = 0; mode < 4; ++mode) {
        EventScheduler::get().reset();
        hw::experiment_dsp_startup_reset();
        auto& profile = hw::experimentDspStartup;
        profile.enabled = true;
        profile.lostDma = mode == 1;
        profile.wrongMail = mode == 2;
        profile.lostMail = mode == 3;
        std::copy_n(context.mmu.get_ptr(0x8042bca0), 32, context.mmu.get_ptr(0x81000000));
        std::fill_n(context.mmu.mem2.begin(), 32, 0xa5);
        bool pending = false;
        bool wrong = false;
        for (unsigned command = 0; command < commands.size(); ++command) {
            if (command == 7 || command == 11) {
                unsigned tries = 0;
                while (!(hw::experiment_dsp_startup_read(context, 0xcc00500a, 2) & 0x20) && ++tries < 10000) {}
                if (tries == 10000) { pending = true; break; }
            }
            const auto& request = commands[command];
            hw::experiment_dsp_startup_write(context, request[0], request[1], request[2]);
            if (request[0] == 0xcc00500a && (request[1] & 1)) {
                unsigned tries = 0;
                while ((hw::experiment_dsp_startup_read(context, 0xcc00500a, 2) & 1) && ++tries < 10000) {}
                if (tries == 10000) { return 11; }
            }
            if (command == 13) {
                unsigned tries = 0;
                while (!(hw::experiment_dsp_startup_read(context, 0xcc005004, 2) & 0x8000) && ++tries < 10000) {}
                if (tries == 10000) { pending = true; break; }
                wrong = hw::experiment_dsp_startup_read(context, 0xcc005006, 2) != 0x4348;
            }
        }
        if (mode == 0) {
            if (pending || wrong || profile.completedDmas != 2 || profile.command != 17 ||
                hw::experiment_dsp_startup_read(context, 0xcc00500a, 2) != 0x804 ||
                hw::experiment_dsp_startup_read(context, 0xcc005022, 2) != 32 ||
                hw::experiment_dsp_startup_read(context, 0xcc005026, 2) != 32 ||
                !std::equal(context.mmu.mem2.begin(), context.mmu.mem2.begin() + 32, context.mmu.get_ptr(0x8042bca0))) { return 12; }
        } else if (mode == 2) {
            if (pending || !wrong) { return 13; }
        } else if (!pending) { return 14; }
        if (g_mmu || g_ctx_ptr) { return 15; }
        std::cout << "DSP_CONTRACT " << mode << ' ' << profile.command << ' ' << profile.completedDmas << ' ' << pending << ' ' << wrong << '\n';
    }
    return 0;
}
