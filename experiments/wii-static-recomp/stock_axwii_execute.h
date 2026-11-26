// Copyright 2008 Dolphin Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "stock_axwii_commands.h"
#include "stock_axwii_buffers.h"
#include "stock_axwii_output.h"
#include "stock_axwii_process.h"
#include "stock_axwii_aux.h"

namespace openshsm::experiment {

template<class Resolve, class ReadByte, class Signal>
inline unsigned execute_axwii_commands(std::span<const uint8_t> bytes, uint32_t profile,
    AxWiiMainBuffers& main, AxWiiRemoteBuffers& remote, uint16_t& output_volume,
    uint16_t& compressor_position, std::array<uint16_t, 3>& aux_volumes,
    Resolve&& resolve, ReadByte&& read_byte, Signal&& signal,
    std::span<const int16_t> coefficient_banks = {}) {
    const auto commands = decode_axwii_commands(bytes, profile);
    unsigned processed_nodes = 0;
    for (const auto& command : commands) {
        const auto address = [&](unsigned index) {
            return uint32_t(command.arguments[index]) << 16 | command.arguments[index + 1];
        };
        switch (command.opcode) {
        case 0:
            setup_axwii_buffers(main, remote, resolve(address(0), 120));
            break;
        case 1:
        case 2:
        case 3:
            add_axwii_lr(main, resolve(address(0), command.opcode == 3 ? 768 : 384),
                command.opcode == 2, command.opcode == 3);
            break;
        case 4:
            processed_nodes += process_axwii_pb_list(address(0), main, remote, resolve, read_byte,
                coefficient_banks, profile);
            break;
        case 5:
        case 6:
        case 7:
            mix_axwii_aux(main, aux_volumes, command.opcode - 5, command.arguments[0],
                address(1), address(3), resolve);
            break;
        case 8:
        case 9: {
            std::array<uint32_t, 6> addresses;
            for (unsigned index = 0; index < addresses.size(); ++index) {
                addresses[index] = address(1 + index * 2);
            }
            upload_axwii_aux_lrsc(main, aux_volumes, command.opcode - 8,
                command.arguments[0], addresses, resolve);
            break;
        }
        case 10: {
            const uint16_t release = command.arguments[1];
            if (release > 10 || compressor_position > 10) {
                throw std::runtime_error("Unverified AXWii compressor release range");
            }
            bool table_needed = compressor_position != 0;
            for (unsigned index = 0; index < 96; ++index) {
                for (unsigned channel = 0; channel < 2; ++channel) {
                    const int64_t sample = main[channel][index];
                    table_needed |= (sample < 0 ? -sample : sample) > command.arguments[0];
                }
            }
            std::span<const uint8_t> table;
            if (table_needed) {
                table = resolve(address(2), 21 * 192);
            }
            compress_axwii_buffers(main, compressor_position, command.arguments[0], release, table);
            break;
        }
        case 11:
        case 12: {
            const auto output = prepare_axwii_output(main, remote, output_volume,
                command.arguments[0], command.opcode == 12);
            commit_axwii_output(output, main, output_volume, address(3), address(1), resolve, signal);
            break;
        }
        case 13: {
            std::array<uint32_t, 4> addresses;
            for (unsigned channel = 0; channel < 4; ++channel) {
                addresses[channel] = address(channel * 2);
            }
            const auto output = prepare_axwii_output(main, remote, output_volume, output_volume, false);
            commit_axwii_wm_output(output, addresses, resolve);
            break;
        }
        case 14:
            return processed_nodes;
        default:
            throw std::runtime_error("Unsupported AXWii execution command");
        }
    }
    throw std::runtime_error("Unterminated AXWii execution");
}

}
