// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_execute.h"
#include "stock_axwii_sample_memory.h"
#include "stock_axwii_coefficients.h"
#include "stock_dsp_capture.h"

namespace openshsm::experiment {

class AxWiiDspExecution {
public:
    enum class MailObservation { Other, BootParameter, BootComplete };

    MailObservation observe(const nwii::runtime::CPUContext& ctx, uint32_t mail) {
        const uint32_t parameter = pending;
        if (pending == 0x80f3a001) {
            firmware_address = mail;
            profile = 0;
            pending = 0;
        } else if (pending == 0x80f3a002) {
            pending = 0;
            profile = 0;
            const auto* bytes = mail == 8192 ? dsp_capture_ram(ctx, firmware_address, mail) : nullptr;
            if (bytes) {
                uint32_t hash = 0;
                for (unsigned index = 0; index < mail; ++index) {
                    hash ^= bytes[index];
                    hash = (hash << 3) | (hash >> 29);
                }
                if (hash == 0x4cc52064) {
                    profile = hash;
                }
            }
        } else if (pending) {
            pending = 0;
        } else if (mail == 0x80f3a001 || mail == 0x80f3a002 ||
                mail == 0x80f3b002 || mail == 0x80f3c002 || mail == 0x80f3d001) {
            pending = mail;
        } else if ((mail & 0xffff0000u) == 0xbabe0000u) {
            command_units = uint16_t(mail);
        }
        if (parameter == 0x80f3d001) {
            return MailObservation::BootComplete;
        }
        if (parameter || pending) {
            return MailObservation::BootParameter;
        }
        return MailObservation::Other;
    }

    template<class Signal>
    unsigned execute(nwii::runtime::CPUContext& ctx, uint32_t address, Signal&& signal) {
        if (profile != 0x4cc52064 || !command_units || command_units > 256 ||
            ctx.mmu.mem1.size() != 24 * 1024 * 1024 + 8 || ctx.mmu.mem2.size() != 64 * 1024 * 1024 + 8) {
            throw std::runtime_error("Unverified AXWii firmware/list/memory configuration");
        }
        const size_t bytes = size_t(command_units) * 2;
        const auto* commands = dsp_capture_ram(ctx, address, bytes);
        if (!commands) {
            throw std::runtime_error("AXWii commands outside backed RAM");
        }
        const auto resolve = [&](uint32_t target, size_t size) {
            const auto* data = dsp_capture_ram(ctx, target, size);
            if (!data) {
                throw std::runtime_error("AXWii target outside backed RAM");
            }
            return std::span(const_cast<uint8_t*>(data), size);
        };
        const AxWiiSampleMemory samples{
            std::span<const uint8_t>(ctx.mmu.mem1).first(ctx.mmu.mem1.size() - 8),
            std::span<const uint8_t>(ctx.mmu.mem2).first(ctx.mmu.mem2.size() - 8),
            0x01ffffffu, 0x03ffffffu};
        const unsigned count = execute_axwii_commands({commands, bytes}, profile, main, remote,
            volume, compressor, aux_volumes, resolve, samples, signal, axwii_free_coefficients);
        command_units = 0;
        return count;
    }

private:
    uint32_t pending = 0, firmware_address = 0, profile = 0;
    uint16_t command_units = 0, volume = 0, compressor = 0;
    std::array<uint16_t, 3> aux_volumes{};
    AxWiiMainBuffers main{};
    AxWiiRemoteBuffers remote{};
};

}
