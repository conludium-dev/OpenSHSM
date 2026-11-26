#include "loader/loader.h"
#include "runtime/cpu_context.h"
#include "functions.h"
#include <algorithm>
#include <charconv>
#include <fstream>
#include <map>
#include <sstream>
#include <stdexcept>
#ifdef SHSM_PROCESSOR_ADAPTER
#include "processor_adapter.h"
#endif

using nwii::runtime::CPUContext;
#ifndef SHSM_BOOT_INITIAL_MSR
#define SHSM_BOOT_INITIAL_MSR 0
#endif
namespace {
std::map<uint32_t, std::string> quarantine;
unsigned calls = 0;

struct BootBoundary : std::runtime_error {
    using std::runtime_error::runtime_error;
};

[[noreturn]] void stop(const char* reason) {
    throw BootBoundary(reason);
}
}

namespace nwii::runtime {
bool g_trace_calls = true;
uint32_t g_watch_addr = 0;
void trace_call(uint32_t address, CPUContext&) {
    std::cout << "BOOT_TRACE address=" << std::hex << address << std::dec << '\n';
    if (++calls > 1000) {
        stop("Function-call budget exceeded");
    }
    auto found = quarantine.find(address);
    if (found != quarantine.end()) {
        throw BootBoundary(found->second);
    }
}
void interpret_step(CPUContext&) { stop("Interpreter fallback forbidden"); }
bool interpret_one(CPUContext&) { stop("Interpreter fallback forbidden"); }
void micro_interpret(CPUContext&, uint32_t, uint32_t) { stop("Interpreter fallback forbidden"); }
bool process_pending_callbacks(CPUContext&) { stop("Scheduler callback service unavailable"); }
bool handle_syscall(CPUContext&) { stop("System-call service unavailable"); }
void init_ipc_client(CPUContext&) { stop("IOS IPC service unavailable"); }
void hle_set_ipc_arm_msg(uint32_t) { stop("IOS IPC service unavailable"); }
void add_recompiled_range(uint32_t, uint32_t) { stop("Dynamic executable range registration unavailable"); }
bool in_recompiled_code(uint32_t) { stop("Dynamic executable range query unavailable"); }
void note_null_call(uint32_t, uint32_t) { stop("Null original indirect call"); }
void watch_hit(uint32_t, uint32_t, int) { stop("Unexpected watch access"); }
uint16_t HW_Reg_Read16(uint32_t) { stop("Wii MMIO read16 unavailable"); }
uint32_t HW_Reg_Read32(uint32_t) { stop("Wii MMIO read32 unavailable"); }
void HW_Reg_Write16(uint32_t, uint16_t) { stop("Wii MMIO write16 unavailable"); }
void HW_Reg_Write32(uint32_t, uint32_t) { stop("Wii MMIO write32 unavailable"); }
void GX_WGPIPE_Write8(uint8_t) { stop("GX pipe write8 unavailable"); }
void GX_WGPIPE_Write16(uint16_t) { stop("GX pipe write16 unavailable"); }
void GX_WGPIPE_Write32(uint32_t) { stop("GX pipe write32 unavailable"); }
void GX_WGPIPE_WriteF32(float) { stop("GX pipe float write unavailable"); }
void GX_WGPIPE_WriteF64(double) { stop("GX pipe double write unavailable"); }
void GX_DL_Snapshot(uint32_t, uint32_t) { stop("GX display-list snapshot unavailable"); }
bool GX_DL_Fetch(uint32_t, uint32_t, std::vector<uint8_t>&) { stop("GX display-list fetch unavailable"); }
}

int main(int argc, char** argv) {
#ifdef SHSM_CACHE_ADAPTER
    if (argc == 2 && std::string(argv[1]) == "--cache-check") {
        nwii::runtime::g_trace_calls = false;
        nwii::runtime::ProcessorContext context;
        context.instructionImages.emplace_back(0x80600000, std::vector<uint8_t>(16, 0x60));
        for (unsigned mode = 0; mode < 5; ++mode) {
            context.hid0 = 0x4000;
            context.msr = mode == 2 ? 0x4000 : 0;
            context.instructionCacheInvalidations = 0;
            std::fill(context.mmu.get_ptr(0x80600000), context.mmu.get_ptr(0x80600000) + 16, mode == 1 ? 0x61 : 0x60);
            auto saved = context.instructionImages;
            if (mode == 3) {
                context.instructionImages.clear();
            }
            context.pc = 0x802130d0;
            context.lr = 0x807f0000;
            unsigned status = 0;
            try {
                if (mode == 4) {
                    nwii::runtime::experiment_write_hid0(context, context.hid0 ^ 0x8000);
                } else {
                    func_802130D0(context);
                }
            } catch (const std::runtime_error&) {
                status = 1;
            }
            std::cout << "CACHE_CASE " << mode << ' ' << status << ' ' << context.hid0 << ' '
                      << context.instructionCacheInvalidations << ' ' << (context.pc == context.lr) << '\n';
            context.instructionImages = std::move(saved);
        }
        return 0;
    }
#endif
#ifdef SHSM_PROCESSOR_ADAPTER
    if (argc == 2 && std::string(argv[1]) == "--processor-check") {
        nwii::runtime::g_trace_calls = false;
        uint32_t prior, value, msr;
        nwii::runtime::ProcessorContext context;
        std::string line;
        while (std::getline(std::cin, line)) {
            std::istringstream input(line);
            std::string tokens[3], extra;
            if (!(input >> tokens[0] >> tokens[1] >> tokens[2]) || input >> extra) {
                return 8;
            }
            uint32_t parsed[3];
            for (unsigned index = 0; index < 3; ++index) {
                const auto decoded = std::from_chars(tokens[index].data(), tokens[index].data() + tokens[index].size(), parsed[index]);
                if (decoded.ec != std::errc() || decoded.ptr != tokens[index].data() + tokens[index].size()) {
                    return 8;
                }
            }
            prior = parsed[0];
            value = parsed[1];
            msr = parsed[2];
            context.gpr.fill(0);
            context.hid2 = prior;
            context.msr = msr;
            context.pc = 0x802107e0;
            context.lr = 0x807f0000;
            context.gpr[3] = value;
            unsigned status = 0;
            bool abi = false;
            try {
                func_802107E0(context);
                abi = context.pc == context.lr && context.gpr[3] == value;
                context.pc = 0x802107d0;
                func_802107D0(context);
                abi &= context.pc == context.lr && context.gpr[3] == context.hid2;
            } catch (const std::runtime_error&) {
                status = 1;
            }
            std::cout << prior << ' ' << value << ' ' << msr << ' ' << status << ' ' << context.hid2 << ' ' << abi << '\n';
        }
        return std::cin.eof() ? 0 : 8;
    }
#endif
    if (argc != 3) {
        return 2;
    }
    std::ifstream policy(argv[2]);
    uint32_t address;
    std::string reason;
    while (policy >> std::hex >> address >> reason) {
        quarantine.emplace(address, reason);
    }
    if (!policy.eof() || quarantine.empty()) {
        return 3;
    }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1]) || executable.entry_point != 0x80006310) {
        return 4;
    }
#ifdef SHSM_PROCESSOR_ADAPTER
    nwii::runtime::ProcessorContext context;
#else
    CPUContext context;
#endif
    for (const auto& section : executable.sections) {
        auto destination = context.mmu.get_ptr(section.address);
        if (!destination || !context.mmu.get_ptr(section.address + section.size - 1)) {
            return 5;
        }
        std::copy(section.data.begin(), section.data.end(), destination);
#ifdef SHSM_CACHE_ADAPTER
        if (section.is_text && !section.data.empty()) {
            context.instructionImages.emplace_back(section.address, section.data);
        }
#endif
    }
    context.gpr.fill(0);
    context.cr.fill({});
    context.pc = executable.entry_point;
    context.lr = 0;
    context.ctr = 0;
    context.xer = 0;
    context.msr = SHSM_BOOT_INITIAL_MSR;
    try {
        func_80006310(context);
        std::cerr << "BOOT_UNPROVEN_RETURN pc=" << std::hex << context.pc << '\n';
        return 6;
    } catch (const std::runtime_error& boundary) {
        std::cout << "BOOT_BOUNDARY pc=" << std::hex << context.pc << " lr=" << context.lr
                  << " msr=" << context.msr << std::dec << " calls=" << calls << " reason=" << boundary.what() << '\n';
        std::cout << "BOOT_REGISTERS";
        for (uint32_t value : context.gpr) {
            std::cout << ' ' << value;
        }
        std::cout << '\n';
        const uint32_t stackTop = context.gpr[1] + 16;
        std::cout << "BOOT_STACK";
        for (uint32_t address = stackTop - 32; address < stackTop + 32; ++address) {
            std::cout << ' ' << static_cast<unsigned>(context.mmu.read8(address));
        }
        std::cout << '\n';
#ifdef SHSM_PROCESSOR_ADAPTER
        std::cout << "BOOT_PROCESSOR hid2=" << std::hex << context.hid2 << std::dec << '\n';
#ifdef SHSM_CACHE_ADAPTER
        std::cout << "BOOT_CACHE hid0=" << std::hex << context.hid0 << std::dec
                  << " invalidations=" << context.instructionCacheInvalidations << '\n';
#endif
#endif
        return 7;
    }
}
