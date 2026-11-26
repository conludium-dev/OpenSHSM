#include "fpscr_adapter.h"

namespace nwii::runtime {
void trace_call(uint32_t address, CPUContext& context);
}

#define trace_call original_trace_call
#define main original_boot_main
#include "mass_boot.cpp"
#undef main
#undef trace_call

namespace nwii::runtime {
void trace_call(uint32_t address, CPUContext& context) {
    std::cout << "FP_STATE " << address << ' ' << context.fpscr;
    for (const auto& field : context.cr) {
        std::cout << ' ' << ((field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0));
    }
    for (double value : context.fpr) {
        std::cout << ' ' << std::bit_cast<uint64_t>(value);
    }
    for (double value : context.ps1) {
        std::cout << ' ' << std::bit_cast<uint64_t>(value);
    }
    std::cout << ' ' << context.ctr << ' ' << context.xer << '\n';
    original_trace_call(address, context);
}
}

#ifndef SHSM_FPSCR_MAIN_NAME
#define SHSM_FPSCR_MAIN_NAME main
#endif
int SHSM_FPSCR_MAIN_NAME(int argc, char** argv) {
    if (argc == 3 && std::string(argv[1]) == "--fpr-init-check") {
        nwii::runtime::g_trace_calls = false;
        nwii::runtime::ProcessorContext context;
        nwii::loader::Executable executable;
        if (!executable.load_dol(argv[2]) || executable.entry_point != 0x80006310) {
            return 4;
        }
        for (const auto& section : executable.sections) {
            auto destination = context.mmu.get_ptr(section.address);
            if (!destination || !context.mmu.get_ptr(section.address + section.size - 1)) {
                return 5;
            }
            std::copy(section.data.begin(), section.data.end(), destination);
        }
        for (unsigned mode = 0; mode < 8; ++mode) {
            context.hid2 = mode < 4 ? 0 : 0xa0000000;
            context.msr = SHSM_BOOT_INITIAL_MSR;
            context.fpscr = 0x12345678;
            context.gpr.fill(0);
            context.gpr[13] = 0x8052e720;
            context.cr.fill({});
            context.pc = 0x80210890;
            context.lr = 0x807f0000;
            for (unsigned index = 0; index < 32; ++index) {
                context.fpr[index] = (index + 1) * (mode + 1);
                context.ps1[index] = -static_cast<double>((index + 1) * (mode + 1));
            }
            func_80210890(context);
            std::cout << "FPR_INIT " << mode << ' ' << context.pc << ' ' << context.msr << ' ' << context.fpscr;
            for (double value : context.fpr) {
                std::cout << ' ' << std::bit_cast<uint64_t>(value);
            }
            for (double value : context.ps1) {
                std::cout << ' ' << std::bit_cast<uint64_t>(value);
            }
            std::cout << '\n';
        }
        return 0;
    }
    if (argc == 2 && std::string(argv[1]) == "--fpscr-check") {
        nwii::runtime::g_trace_calls = false;
        nwii::runtime::ProcessorContext context;
        std::string line;
        while (std::getline(std::cin, line)) {
            std::istringstream input(line);
            std::string tokens[5], extra;
            uint64_t parsed[5];
            for (unsigned index = 0; index < 5; ++index) {
                if (!(input >> tokens[index])) {
                    return 8;
                }
                auto decoded = std::from_chars(tokens[index].data(), tokens[index].data() + tokens[index].size(), parsed[index]);
                if (decoded.ec != std::errc() || decoded.ptr != tokens[index].data() + tokens[index].size()
                    || (index != 1 && parsed[index] > UINT32_MAX)) {
                    return 8;
                }
            }
            if (input >> extra || (parsed[2] >> 26) != 63 || ((parsed[2] >> 1) & 1023) != 711) {
                return 8;
            }
            context.fpr.fill(1.0);
            context.ps1.fill(2.0);
            context.fpr[(parsed[2] >> 11) & 31] = std::bit_cast<double>(parsed[1]);
            context.fpscr = parsed[0];
            context.msr = parsed[3];
            for (unsigned index = 0; index < 8; ++index) {
                const auto value = (parsed[4] >> ((7 - index) * 4)) & 15;
                context.cr[index] = { };
                context.cr[index].lt = value & 8;
                context.cr[index].gt = value & 4;
                context.cr[index].eq = value & 2;
                context.cr[index].so = value & 1;
            }
            unsigned status = 0;
            try {
                nwii::runtime::experiment_mtfsf(context, parsed[2]);
            } catch (const std::runtime_error&) {
                status = 1;
            }
            uint32_t cr = 0;
            for (const auto& field : context.cr) {
                cr = (cr << 4) | (field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0);
            }
            std::cout << status << ' ' << context.fpscr << ' ' << cr << ' '
                      << std::bit_cast<uint64_t>(context.fpr[(parsed[2] >> 11) & 31]) << '\n';
        }
        return std::cin.eof() ? 0 : 8;
    }
    return original_boot_main(argc, argv);
}
