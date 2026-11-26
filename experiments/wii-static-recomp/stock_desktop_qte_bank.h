#pragma once
#include <processor_adapter.h>
#include <array>
#include <cstdint>
#include <cstring>

namespace openshsm::experiment {

class DesktopQTEBank {
public:
    // The caller supplies a verified generated TXD whose bytes remain stable until Load returns.
    bool begin(nwii::runtime::CPUContext& ctx, uint32_t entry, const uint8_t* payload,
        uint32_t bytes, const std::array<uint8_t, 16>& identifier) {
        uint8_t nonzero = 0;
        for (uint8_t value : identifier) {
            nonzero |= value;
        }
        if (phase != Phase::Empty || payload == nullptr || bytes == 0 || bytes > 65536
            || nonzero == 0
            || (entry != 0x800EB5EC && entry != 0x800EBB10)
            || ctx.pc != entry || ctx.gpr[13] != 0x8052E720
            || !span(ctx.gpr[1], 8) || (ctx.gpr[1] & 15) != 0
            || ctx.in_callback || ctx.callback_depth != 0) {
            return false;
        }
        saved = {ctx.gpr, ctx.fpr, ctx.ps1, ctx.cr, ctx.lr, ctx.ctr, ctx.xer, ctx.pc,
            ctx.srr0, ctx.srr1, ctx.msr, ctx.fpscr, ctx.gqr, ctx.sprg};
        reservation = ctx.reservation_addr;
        thread = ctx.mmu.read32(0x800000E4);
        os_context = ctx.mmu.read32(0x800000D8);
        data = payload;
        size = bytes;
        guid = identifier;
        phase = Phase::Allocate;
        ctx.gpr[3] = bytes + 0x100;
        ctx.gpr[4] = 2;
        ctx.gpr[5] = 0x40000;
        call(ctx, 0x801AD194);
        return true;
    }

    bool resume(nwii::runtime::CPUContext& ctx) {
        if (!pending() || ctx.pc != saved.pc || ctx.lr != saved.pc
            || ctx.gpr[1] != saved.gpr[1] || ctx.gpr[13] != saved.gpr[13]
            || ctx.mmu.read32(0x800000E4) != thread
            || ctx.mmu.read32(0x800000D8) != os_context
            || ctx.in_callback || ctx.callback_depth != 0) {
            return false;
        }
        if (phase == Phase::Allocate) {
            storage = ctx.gpr[3];
            if (!span(storage, size + 0x100)) {
                phase = Phase::Failed;
                restore(ctx);
                return false;
            }
            std::memset(ctx.mmu.get_ptr(storage), 0, 0x100);
            std::memcpy(ctx.mmu.get_ptr(storage + 0x100), data, size);
            std::memcpy(ctx.mmu.get_ptr(storage + 0x20), guid.data(), guid.size());
            std::memcpy(ctx.mmu.get_ptr(storage + 0x40), "rwID_TEXDICTIONARY", 18);
            const uint32_t stream = storage + 0x80;
            ctx.mmu.write32(stream, 3);
            ctx.mmu.write32(stream + 16, size);
            ctx.mmu.write32(stream + 20, storage + 0x100);
            ctx.gpr[3] = storage;
            ctx.gpr[4] = storage + 0x20;
            ctx.gpr[5] = storage + 0x40;
            ctx.gpr[6] = 0;
            ctx.gpr[7] = stream;
            ctx.gpr[8] = size;
            phase = Phase::Load;
            call(ctx, 0x801ABB88);
            return true;
        }
        if (phase == Phase::Load) {
            resource = ctx.gpr[3];
            valid = span(resource, 0x34) && ctx.mmu.read32(resource) == 0x8042B2EC
                && ctx.mmu.read32(resource + 0x1C) > 0
                && span(ctx.mmu.read32(resource + 0x14), 16)
                && std::memcmp(ctx.mmu.get_ptr(resource + 0x24), guid.data(), guid.size()) == 0
                && ctx.mmu.read32(storage + 0x80 + 12) == size;
            ctx.gpr[3] = storage;
            phase = Phase::FreeInput;
            call(ctx, 0x801AD0E4);
            return true;
        }
        if (phase == Phase::FreeInput) {
            storage = 0;
            data = nullptr;
            phase = valid ? Phase::Ready : Phase::Failed;
            restore(ctx);
            return false;
        }
        resource = 0;
        phase = Phase::Empty;
        restore(ctx);
        return false;
    }

    bool release(nwii::runtime::CPUContext& ctx, uint32_t entry) {
        if (phase != Phase::Ready || ctx.pc != entry
            || (entry != 0x800EB5EC && entry != 0x800EBB10)
            || ctx.gpr[13] != 0x8052E720 || !span(ctx.gpr[1], 8)
            || (ctx.gpr[1] & 15) != 0 || ctx.in_callback || ctx.callback_depth != 0
            || !span(resource, 0x34) || ctx.mmu.read32(resource) != 0x8042B2EC
            || ctx.mmu.read32(resource + 0x1C) == 0
            || std::memcmp(ctx.mmu.get_ptr(resource + 0x24), guid.data(), guid.size()) != 0) {
            return false;
        }
        saved = {ctx.gpr, ctx.fpr, ctx.ps1, ctx.cr, ctx.lr, ctx.ctr, ctx.xer, ctx.pc,
            ctx.srr0, ctx.srr1, ctx.msr, ctx.fpscr, ctx.gqr, ctx.sprg};
        reservation = ctx.reservation_addr;
        thread = ctx.mmu.read32(0x800000E4);
        os_context = ctx.mmu.read32(0x800000D8);
        ctx.gpr[3] = resource;
        phase = Phase::Release;
        call(ctx, 0x801ABD94);
        return true;
    }

    uint32_t handle() const {
        return phase == Phase::Ready ? resource : 0;
    }

    bool pending() const {
        return phase == Phase::Allocate || phase == Phase::Load
            || phase == Phase::FreeInput || phase == Phase::Release;
    }

    bool empty() const {
        return phase == Phase::Empty;
    }

private:
    enum class Phase { Empty, Allocate, Load, FreeInput, Ready, Release, Failed };

    static bool span(uint32_t address, uint32_t bytes) {
        return (address & 3) == 0
            && ((address >= 0x80000000 && uint64_t(address) + bytes <= 0x81800000)
                || (address >= 0x90000000 && uint64_t(address) + bytes <= 0x94000000));
    }

    void call(nwii::runtime::CPUContext& ctx, uint32_t address) const {
        ctx.pc = address;
        ctx.lr = saved.pc;
    }

    void restore(nwii::runtime::CPUContext& ctx) const {
        ctx.gpr = saved.gpr;
        ctx.fpr = saved.fpr;
        ctx.ps1 = saved.ps1;
        ctx.cr = saved.cr;
        ctx.lr = saved.lr;
        ctx.ctr = saved.ctr;
        ctx.xer = saved.xer;
        ctx.pc = saved.pc;
        ctx.srr0 = saved.srr0;
        ctx.srr1 = saved.srr1;
        ctx.msr = saved.msr;
        ctx.fpscr = saved.fpscr;
        ctx.gqr = saved.gqr;
        ctx.sprg = saved.sprg;
        ctx.reservation_addr = reservation;
    }

    Phase phase = Phase::Empty;
    nwii::runtime::CPUContext::BackupState saved{};
    uint32_t reservation = 0, thread = 0, os_context = 0, storage = 0, size = 0, resource = 0;
    const uint8_t* data = nullptr;
    std::array<uint8_t, 16> guid{};
    bool valid = false;
};

}
