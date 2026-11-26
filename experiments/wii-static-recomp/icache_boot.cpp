#include "icache_adapter.h"
#define SHSM_FPSCR_MAIN_NAME fpscr_boot_main
#include "fpscr_boot.cpp"
#undef SHSM_FPSCR_MAIN_NAME

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--icache-check") {
        nwii::runtime::g_trace_calls = false;
        nwii::runtime::ProcessorContext context;
        for (unsigned mode = 0; mode < 9; ++mode) {
            context.hid0 = mode == 1 || mode == 7 ? 0x8000 : 0;
            context.msr = mode == 4 ? 0x4030 : 0x30;
            context.instructionCacheInvalidations = 0;
            context.instructionImages = {{0x80600000, std::vector<uint8_t>(16, 0x60)}};
            std::fill(context.mmu.get_ptr(0x80600000), context.mmu.get_ptr(0x80600000) + 16, mode == 2 ? 0x61 : 0x60);
            if (mode == 3) {
                context.instructionImages.clear();
            }
            if (mode == 6) {
                context.instructionImages[0].second.clear();
            }
            context.pc = 0x802130e0;
            context.lr = 0x807f0000;
            unsigned status = 0;
            try {
                if (mode == 5 || mode == 7 || mode == 8) {
                    nwii::runtime::experiment_write_hid0_icache(context, mode == 5 ? 0x4000 : mode == 7 ? 0 : 0x8800);
                } else {
                    func_802130E0(context);
                }
            } catch (const std::runtime_error&) {
                status = 1;
            }
            std::cout << "ICACHE_CASE " << mode << ' ' << status << ' ' << context.hid0 << ' '
                      << context.instructionCacheInvalidations << ' ' << (context.pc == context.lr) << '\n';
        }
        return 0;
    }
    return fpscr_boot_main(argc, argv);
}
