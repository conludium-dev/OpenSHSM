#include "exi_getid_frontend.h"
#include "loader-bat-seed.h"
#define ProcessorContext SeededBatContext
#define main unused_boot_main
#define process_pending_callbacks unused_boot_callback
#include "mass_boot.cpp"
#undef main
#undef process_pending_callbacks
#undef ProcessorContext

namespace nwii::runtime {
bool process_pending_callbacks(CPUContext& context) {
    if (context.inst_count > 100000) {
        throw std::runtime_error("GetID instruction budget exceeded");
    }
    return experiment_boot_poll(context);
}
}

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc < 2 || argc > 3) {
        return 2;
    }
    const std::string mode = argc == 3 ? argv[2] : "normal";
    if (mode != "normal" && mode != "lost" && mode != "wrong" && mode != "guards") {
        return 2;
    }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) {
        return 3;
    }
    SeededBatContext context;
    for (const auto& section : executable.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
        if (section.is_text) {
            context.instructionImages.emplace_back(section.address, section.data);
        }
    }
    hw::register_pi(MMIODispatcher::get());
    hw::experiment_register_exi_masks(MMIODispatcher::get());
    hw::experiment_register_getid_transfer(MMIODispatcher::get());
    hw::pi_intsr = 0x10000;
    g_trace_calls = false;
    memory_context(context).hid0 = 0xc200;
    context.hid2 = 0xa0000000;
    if (mode == "guards") {
        context.msr = 0x2030;
        const auto snapshot = [] {
            return std::array<uint32_t, 8>{hw::experimentExiMaskState[0], hw::experimentExiMaskState[1], hw::experimentExiMaskState[2],
                hw::experimentExiTransfer.control, hw::experimentExiTransfer.data, hw::experimentExiTransfer.phase,
                hw::experimentExiTransfer.command, hw::pi_intsr.load()};
        };
        const std::array<std::function<void()>, 8> invalid{
            [&] { experiment_getid_write32(context, 0xcd006800, 0x80); },
            [&] { experiment_getid_write32(context, 0xcd006800, 0x80000000); },
            [&] { experiment_getid_write32(context, 0xcd00680c, 0x31); },
            [&] { experiment_getid_write32(context, 0xcd006810, 1); },
            [&] { experiment_getid_write32(context, 0xcd006024, 1); },
            [&] { MMIODispatcher::get().read16(0xcd006810); },
            [&] { experiment_getid_read32(context, 0xcd006804); },
            [&] { experiment_getid_write32(context, 0xcc003000, 0x10); }
        };
        for (const auto& test : invalid) {
            const auto before = snapshot();
            bool refused = false;
            try {
                test();
            } catch (const std::runtime_error&) {
                refused = true;
            }
            if (!refused || before != snapshot()) {
                return 12;
            }
        }
        std::cout << "GETID_GUARDS 8\n";
        return 0;
    }
    for (unsigned index = 0; index < 16; ++index) {
        context.gpr.fill(0);
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[3] = 0;
        context.gpr[4] = 2;
        context.gpr[5] = 0x80500000;
        context.msr = 0x2030;
        context.fpscr = index >= 8 ? 4 : 0;
        context.lr = 0x807f0000;
        context.pc = 0x8020ecd0;
        context.inst_count = 0;
        bootPollChecks = 0;
        context.is_running = true;
        for (unsigned offset = 0; offset < 64; offset += 4) {
            bat_memory_write32(context, 0x80491f50 + offset, 0);
        }
        bat_memory_write32(context, 0x8052aa08, 0);
        bat_memory_write32(context, 0x80500000, 0xa5a5a5a5);
        hw::experiment_getid_csr_write(0xcd006800, 0);
        hw::experiment_getid_csr_write(0xcd006800, 0x2000);
        hw::experimentExiTransfer.phase = 0;
        hw::experimentExiTransfer.command = false;
        hw::experimentExiTransfer.observations.clear();
        hw::experimentExiTransfer.loseCompletion = mode == "lost";
        hw::experimentExiTransfer.wrongResponse = mode == "wrong";
        const auto before = hw::experimentExiMaskState[0];
        const auto causeBefore = hw::pi_intsr.load();
        try {
            func_8020ECD0(context);
        } catch (const std::runtime_error& failure) {
            std::cerr << "GETID_BOUNDARY " << std::hex << context.pc << ' ' << failure.what() << '\n';
            return mode == "lost" && (hw::experimentExiTransfer.control & 1) ? 20 : 10;
        }
        if (context.pc != 0x807f0000 || context.msr != 0x2030 || context.fpscr != (index >= 8 ? 4u : 0u)) {
            return 11;
        }
        std::cout << "GETID_CASE " << index << ' ' << context.gpr[3] << ' ' << bat_memory_read32(context, 0x80500000)
                  << ' ' << before << ' ' << hw::experimentExiMaskState[0] << ' ' << causeBefore << ' ' << hw::pi_intsr.load()
                  << ' ' << hw::experimentExiTransfer.control << ' ' << hw::experimentExiTransfer.data
                  << ' ' << bat_memory_read32(context, 0x8052aa08);
        for (unsigned offset = 0; offset < 64; offset += 4) {
            std::cout << ' ' << bat_memory_read32(context, 0x80491f50 + offset);
        }
        std::cout << '\n';
        for (const auto& phase : hw::experimentExiTransfer.observations) {
            std::cout << "GETID_PHASE " << index;
            for (auto value : phase) {
                std::cout << ' ' << value;
            }
            std::cout << '\n';
        }
    }
    return 0;
}
