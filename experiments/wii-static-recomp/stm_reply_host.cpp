#include "ipc_open_packet.h"
#include "runtime/devices.h"
#include <cstring>
#include <iomanip>

namespace nwii::runtime {
inline unsigned stmProduced = 0;
bool process_pending_callbacks(CPUContext& context) {
    if (context.inst_count > 100000) { throw std::runtime_error("STM reply instruction budget"); }
    if (context.pc == 0x807f0000 && context.msr == 0xa032) {
        EventScheduler::get().advance(context, EventScheduler::get().now() + 1);
        hw::experiment_ipc_irq_update();
        if (stmProduced == 1 && !(hw::pi_intsr.load() & hw::pi_intmr.load()) &&
            bat_memory_read16(context, 0x806902c8) == 1) {
            throw std::runtime_error("Original reply/wakeup returned");
        }
    }
    return experiment_boot_poll(context);
}
}
extern "C" void run_game(nwii::runtime::CPUContext&);

int main(int argc, char** argv) {
    using namespace nwii::runtime;
    if (argc != 2 && !(argc == 3 && std::string(argv[2]) == "guards")) { return 2; }
    nwii::loader::Executable executable;
    if (!executable.load_dol(argv[1])) { return 3; }
    IOSKernel::get().init();
    IOSKernel::get().register_device(devices::create_stm_device());
    for (unsigned index = 0; index < 16; ++index) {
        SeededBatContext context;
        for (const auto& section : executable.sections) {
            std::copy(section.data.begin(), section.data.end(), context.mmu.get_ptr(section.address));
            if (section.is_text) { context.instructionImages.emplace_back(section.address, section.data); }
        }
        context.msr = 0x2032;
        context.hid0 = 0xc200;
        context.hid2 = 0xa0000000;
        g_trace_calls = false;
        for (unsigned slot = 0; slot < 38; ++slot) {
            auto word = bat_memory_read32(context, 0x80211ba0 + slot * 4);
            bat_memory_write32(context, 0x80000500 + slot * 4, slot == 26 ? 0x38600004 : word);
        }
        for (unsigned slot = 0; slot < ipcThreadWords.size(); ++slot) {
            bat_memory_write32(context, 0x80492658 + slot * 4, ipcThreadWords[slot]);
            bat_memory_write32(context, 0x80690000 + slot * 4, ipcThreadWords[slot]);
        }
        const uint32_t physical = 0x135e0020 + index * 64;
        const uint32_t pathAddress = index < 8 ? 0x4398f0 : 0x6a1000;
        const char* path = index < 8 ? "/dev/stm/immediate" : "/dev/openshsm_missing";
        auto* packet = context.mmu.get_ptr(physical);
        std::memset(packet, 0, 64);
        std::memcpy(context.mmu.get_ptr(pathAddress), path, std::strlen(path) + 1);
        experiment_ipc_store_be32(packet, 1);
        experiment_ipc_store_be32(packet + 12, pathAddress);
        experiment_ipc_store_be32(packet + 44, 0x80690000);
        experiment_ipc_store_be32(packet + 48, 0x80690000);
        for (const auto& seed : std::vector<std::array<uint32_t, 2>>{
            {0x800000c0, 0x492658}, {0x800000c4, 0xf7fff7e0}, {0x800000c8, 0}, {0x800000d4, 0x80492658},
            {0x800000d8, 0x80492658}, {0x800000e4, 0x80492658}, {0x80003010, 0x80217c60},
            {0x8052aad8, 0x80003040}, {0x800030ac, 0x80241f00}, {0x8052ab00, 0}, {0x8052ab04, 0}, {0x8052ab08, 0},
            {0x80528b70, 0}, {0x804b2a80, 1}, {0x804b2a84, 1}, {0x804b2a88, 1}, {0x804b2a8c, 1},
            {0x806902c8, 0x00040001}, {0x806902cc, 0}, {0x806902d0, 17}, {0x806902d4, 17},
            {0x806902dc, (physical | 0x80000000) + 44}, {0x806902e0, 0}, {0x806902e4, 0}}) {
            bat_memory_write32(context, seed[0], seed[1]);
        }
        for (unsigned offset = 0; offset < 256; offset += 4) { bat_memory_write32(context, 0x80492970 + offset, 0); }
        hw::register_pi(MMIODispatcher::get());
        hw::experimentSiQuery.interruptProfile = true;
        hw::pi_intsr = 0x14000;
        hw::pi_intmr = 0x40f8;
        hw::ipc_ppc_ctrl = 0x32;
        hw::experimentPpcFlags = 0x40000000;
        hw::ipc_ppc_msg = physical;
        hw::ipc_arm_msg = hw::ipc_arm_ctrl = 0;
        experimentStmIrq = true;
        context.gpr[1] = 0x80540000;
        context.gpr[2] = 0x805335e0;
        context.gpr[13] = 0x8052e720;
        context.gpr[30] = 0xc0680000 + index * 736;
        context.msr = 0xa032;
        context.pc = context.lr = 0x807f0000;
        context.is_running = true;
        if (argc == 3) {
            for (unsigned test = 0; test < 12; ++test) {
                experimentStmIrq = true;
                context.msr = 0x2030;
                context.pc = test < 9 ? 0x80241c20 : test < 11 ? 0x80241c30 : 0x80241cec;
                context.lr = test < 9 ? 0x80241cc8 : 0x80241cec;
                hw::ipc_ppc_ctrl = test == 11 ? 0x30 : 0x34;
                hw::ipc_ppc_msg = physical;
                hw::ipc_arm_msg = physical;
                hw::ipc_arm_ctrl = 0;
                hw::pi_intmr = 0x40f8;
                context.hid0 = 0xc200;
                context.in_callback = false;
                if (test == 0) { experimentStmIrq = false; }
                if (test == 1) { context.msr = 0xa032; }
                if (test == 2 || test == 10) { context.lr = 0x807f0000; }
                if (test == 3) { hw::pi_intmr = 0xf8; }
                if (test == 4) { hw::ipc_arm_msg = physical + 32; }
                if (test == 5) { hw::ipc_ppc_msg = physical + 1; }
                if (test == 6) { hw::ipc_ppc_ctrl = 0x32; }
                if (test == 7) { context.hid0 = 0xc208; }
                if (test == 8) { context.in_callback = true; }
                const auto snapshot = [&] {
                    const auto state = hw::experiment_ipc_snapshot();
                    return std::array<uint64_t, 10>{state.ppcMessage, state.armMessage, state.ppcControl, state.armControl,
                        state.ppcMask, uint64_t(state.delay), hw::pi_intsr.load(), hw::pi_intmr.load(), context.srr0, context.srr1};
                };
                const auto before = snapshot();
                std::array<uint8_t, 64> beforePacket;
                std::copy(packet, packet + 64, beforePacket.begin());
                bool refused = false;
                try {
                    if (test < 9) { experiment_ipc_ack_read(context, 0xcd000008); }
                    else if (test < 11) { experiment_ipc_ack_write(context, 0xcd000004, test == 9 ? 0x31 : 0x34); }
                    else { experiment_ipc_ack_clear(context, 0xcd000030, 0); }
                } catch (const std::runtime_error&) { refused = true; }
                if (!refused || before != snapshot() || !std::equal(beforePacket.begin(), beforePacket.end(), packet)) { return 9; }
            }
            std::cout << "STM_REPLY_GUARDS 12\n";
            return 0;
        }
        EventScheduler::get().reset();
        bootPollChecks = siExternalEntries = stmProduced = 0;
        hw::experiment_fixture_reply_after(physical, 1, [physical](CPUContext& active, uint64_t) {
#ifndef SHSM_MISSING_STM_REPLY
            experiment_ipc_open_packet(active, physical);
#ifdef SHSM_WRONG_STM_REPLY
            experiment_ipc_store_be32(active.mmu.get_ptr(physical) + 4, 0x42);
#endif
            ++stmProduced;
#endif
        });
        try { run_game(context); }
        catch (const std::runtime_error& failure) {
            if (std::string(failure.what()) != "Original reply/wakeup returned") {
                std::cout << "STM_REPLY_BOUNDARY " << index << ' ' << std::hex << context.pc << ' ' << context.lr << ' '
                    << context.msr << std::dec << " entries=" << siExternalEntries << " produced=" << stmProduced
                    << " reason=" << failure.what() << '\n';
                return 7;
            }
        }
        std::cout << "STM_REPLY_CASE " << index << ' ' << context.msr << ' ' << context.pc << ' ' << context.gpr[1] << ' '
            << context.gpr[2] << ' ' << context.gpr[13] << ' ' << context.gpr[30] << ' ' << hw::ipc_ppc_ctrl << ' '
            << hw::ipc_arm_msg << ' ' << hw::pi_intsr.load() << ' ' << siExternalEntries << ' ' << stmProduced;
        for (uint32_t address : {0x80528b70u, 0x8052ab00u, 0x8052ab04u, 0x8052ab08u, 0x800000e4u,
            0x804929f8u, 0x804929fcu, 0x806902c8u, 0x806902d0u, 0x806902dcu, 0x806902e0u, 0x806902e4u}) {
            std::cout << ' ' << bat_memory_read32(context, address);
        }
        std::cout << '\n';
        for (bool cached : {false, true}) {
            std::cout << (cached ? "STM_REPLY_CACHED " : "STM_REPLY_PHYSICAL ") << index << ' ' << std::hex << std::setfill('0');
            for (unsigned offset = 0; offset < 64; ++offset) {
                std::cout << std::setw(2) << unsigned(bat_memory_read8(context, physical + offset + (cached ? 0x80000000 : 0xc0000000)));
            }
            std::cout << std::dec << '\n';
        }
    }
    return 0;
}
