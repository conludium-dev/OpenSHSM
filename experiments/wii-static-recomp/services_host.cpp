#include "loader/loader.h"
#include "runtime/cpu_context.h"
#include <algorithm>
#include <bit>
#include <iomanip>
#include <stdexcept>

using nwii::runtime::CPUContext;
void func_800C770C(CPUContext&);
void func_800C7720(CPUContext&);
void func_800ED314(CPUContext&);
void func_800ED3C8(CPUContext&);
void func_800F3D94(CPUContext&);
void func_800F3E30(CPUContext&);
void func_800F3E60(CPUContext&);
void func_800F3EC0(CPUContext&);

struct ExternalBoundary {};
void func_800374F4(CPUContext&) { throw ExternalBoundary{}; }
void func_800ED8C8(CPUContext&) { throw ExternalBoundary{}; }
void func_800F7524(CPUContext&) { throw ExternalBoundary{}; }

namespace nwii::runtime {
bool g_trace_calls = false;
uint32_t g_watch_addr = 0;
void trace_call(uint32_t, CPUContext&) { throw std::runtime_error("Unexpected instrumentation"); }
void interpret_step(CPUContext&) { throw std::runtime_error("Interpreter fallback forbidden"); }
bool process_pending_callbacks(CPUContext&) { return false; }
void note_null_call(uint32_t, uint32_t) { throw std::runtime_error("Null indirect call forbidden"); }
void watch_hit(uint32_t, uint32_t, int) { throw std::runtime_error("Unexpected watch access"); }
uint32_t HW_Reg_Read32(uint32_t) { throw std::runtime_error("Unexpected hardware read"); }
void HW_Reg_Write32(uint32_t, uint32_t) { throw std::runtime_error("Unexpected hardware write"); }
void GX_WGPIPE_Write32(uint32_t) { throw std::runtime_error("Unexpected GX write"); }
}

void dispatch(CPUContext& context) {
    const uint32_t pc = context.pc;
    if (pc >= 0x800c770c && pc < 0x800c7720) {
        func_800C770C(context);
    } else if (pc >= 0x800c7720 && pc < 0x800c7734) {
        func_800C7720(context);
    } else if (pc >= 0x800ed314 && pc < 0x800ed3c8) {
        func_800ED314(context);
    } else if (pc >= 0x800ed3c8 && pc < 0x800ed8c8) {
        func_800ED3C8(context);
    } else if (pc >= 0x800f3d94 && pc < 0x800f3e30) {
        func_800F3D94(context);
    } else if (pc >= 0x800f3e30 && pc < 0x800f3e5c) {
        func_800F3E30(context);
    } else if (pc >= 0x800f3e60 && pc < 0x800f3ec0) {
        func_800F3E60(context);
    } else if (pc >= 0x800f3ec0 && pc < 0x800f3f30) {
        func_800F3EC0(context);
    } else {
        throw ExternalBoundary{};
    }
}

int main(int argc, char** argv) {
    if (argc != 2) {
        return 2;
    }
    nwii::loader::Executable dol;
    if (!dol.load_dol(argv[1])) {
        return 3;
    }
    CPUContext context;
    for (const auto& section : dol.sections) {
        std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
    }
    constexpr uint32_t host = 0x80600000, object = 0x80604000, vtable = 0x80605000;
    constexpr uint32_t stack = 0x80700000, sentinel = 0x807f0000;
    constexpr uint32_t table = 0x80477328;
    const uint32_t entries[] = {0x800ed3c8, 0x800f3d94, 0x800f3e30, 0x800f3e60, 0x800f3ec0, 0x800ed314};
    uint32_t kind, value, argument, policy, present, disabled;
    while (std::cin >> kind >> value >> argument >> policy >> present >> disabled) {
        if (kind >= 6 || present > 1 || disabled > 1) {
            return 4;
        }
        std::fill(context.mmu.get_ptr(host), context.mmu.get_ptr(host) + 0x3000, 0);
        std::fill(context.mmu.get_ptr(stack - 128), context.mmu.get_ptr(stack + 32), 0);
        std::fill(context.mmu.get_ptr(object), context.mmu.get_ptr(object) + 32, 0);
        std::fill(context.mmu.get_ptr(vtable), context.mmu.get_ptr(vtable) + 32, 0);
        if (present) {
            for (uint32_t offset = 0x1e90; offset <= 0x1fa4; offset += 4) {
                context.mmu.write32(host + offset, object);
            }
            context.mmu.write32(object, vtable);
            context.mmu.write32(vtable + 16, 0x807e0000);
        }
        if (disabled) {
            std::fill(context.mmu.get_ptr(host + 0x1fa8), context.mmu.get_ptr(host + 0x1fb0), 0xff);
        }
        const std::vector<uint8_t> hostBefore(context.mmu.get_ptr(host), context.mmu.get_ptr(host) + 0x3000);
        for (uint32_t index = 0; index < 17; ++index) {
            context.mmu.write32(table + index * 4, index == 4 || index == 7 || index == 16 ? value : 0xabcdef01);
        }
        context.mmu.write32(0x80529d20, host);
        context.mmu.write32(0x805292f8, host);
        for (uint32_t index = 0; index < 32; ++index) {
            context.gpr[index] = 0x12340000 + index * 0x100;
        }
        context.gpr[1] = stack;
        context.gpr[2] = 0x805335e0;
        context.gpr[3] = host;
        context.gpr[4] = argument;
        context.gpr[5] = policy;
        context.gpr[13] = 0x8052e720;
        context.cr.fill({});
        context.xer = 0;
        context.ctr = 0;
        context.lr = sentinel;
        context.pc = entries[kind];
        bool external = false;
        try {
            unsigned budget = 100;
            while (context.pc != sentinel) {
                if (!budget--) {
                    throw std::runtime_error("Dispatcher budget exhausted");
                }
                dispatch(context);
            }
        } catch (const ExternalBoundary&) {
            external = true;
        }
        uint32_t condition = 0;
        for (const auto& field : context.cr) {
            condition = (condition << 4) | (field.lt ? 8 : 0) | (field.gt ? 4 : 0) | (field.eq ? 2 : 0) | (field.so ? 1 : 0);
        }
        std::cout << external << ' ' << context.pc << ' ' << context.lr << ' ' << context.ctr << ' ' << condition;
        for (uint32_t value : context.gpr) {
            std::cout << ' ' << value;
        }
        for (uint32_t index = 0; index < 17; ++index) {
            std::cout << ' ' << context.mmu.read32(table + index * 4);
        }
        std::cout << ' ';
        for (uint32_t address = stack - 128; address < stack + 32; ++address) {
            std::cout << std::hex << std::setfill('0') << std::setw(2) << static_cast<unsigned>(context.mmu.read8(address));
        }
        std::cout << std::dec << ' ' << std::equal(hostBefore.begin(), hostBefore.end(), context.mmu.get_ptr(host)) << '\n';
    }
}
