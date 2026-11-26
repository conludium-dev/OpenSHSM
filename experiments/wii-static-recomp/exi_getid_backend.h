#pragma once
#include "exi_mask_backend.h"
#include <vector>
#include <functional>

namespace nwii::runtime::hw {
struct ExperimentExiTransfer {
    uint32_t control = 0;
    uint32_t data = 0;
    unsigned phase = 0;
    bool command = false;
    bool loseCompletion = false;
    bool wrongResponse = false;
    bool uartAllowed = false;
    bool sramAllowed = false;
    bool loseDmaCompletion = false;
    uint32_t dmaAddress = 0;
    uint32_t dmaLength = 0;
    std::array<uint8_t, 64> sramResponse{};
    std::function<void(uint32_t, const std::array<uint8_t, 64>&)> dmaWrite;
    uint32_t uartCommand = 0;
    std::vector<uint8_t> uartBytes;
    std::vector<std::array<uint32_t, 4>> observations;
};
inline ExperimentExiTransfer experimentExiTransfer;

inline void experiment_getid_update_pi() {
    bool asserted = false;
    for (unsigned channel = 0; channel < 3; ++channel) {
        const auto csr = experimentExiMaskState[channel];
        asserted |= ((csr & 1) && (csr & 2)) || ((csr & 4) && (csr & 8))
            || (channel < 2 && (csr & 0x400) && (csr & 0x800));
    }
    if (asserted) {
        pi_intsr.fetch_or(0x10);
    } else {
        pi_intsr.fetch_and(~0x10u);
    }
}

inline void experiment_getid_csr_write(uint32_t address, uint32_t value) {
    if (address < 0xcd006800 || address > 0xcd006828 || (address - 0xcd006800) % 20) {
        throw std::runtime_error("GetID CSR address unverified");
    }
    const auto channel = (address - 0xcd006800) / 20;
    const auto selected = value & 0x380;
    const bool uartSelected = channel == 0 && selected == 0x100 && experimentExiTransfer.uartAllowed && (value & 0x70) == 0x40;
    const bool sramSelected = channel == 0 && selected == 0x100 && experimentExiTransfer.sramAllowed && (value & 0x70) == 0x30;
    if ((value & ~0x3fffu) || (channel == 0 && selected != 0 && selected != 0x200 && !uartSelected && !sramSelected)
        || (channel == 1 && selected != 0 && selected != 0x80) || (channel == 2 && selected)) {
        throw std::runtime_error("GetID CSR device or fields unverified");
    }
    const uint32_t writable = channel == 0 ? 0x27f5 : channel == 1 ? 0x7f5 : 0x3f5;
    auto csr = (experimentExiMaskState[channel] & ~writable) | (value & writable);
    csr &= ~(value & (channel < 2 ? 0x80a : 0xa));
    if (uartSelected && (experimentExiMaskState[0] & 0x380) != 0x100) {
        experimentExiTransfer.phase = 0;
        experimentExiTransfer.command = false;
        experimentExiTransfer.uartCommand = 0;
    }
    if (sramSelected && (experimentExiMaskState[0] & 0x3f0) != 0x130) {
        experimentExiTransfer.phase = 0;
        experimentExiTransfer.command = false;
        experimentExiTransfer.dmaAddress = 0;
        experimentExiTransfer.dmaLength = 0;
    }
    experimentExiMaskState[channel] = csr;
    experiment_getid_update_pi();
}

inline void experiment_register_getid_transfer(MMIODispatcher& dispatcher) {
    for (const uint32_t base : {0xcd006804u, 0xcd006808u}) {
        dispatcher.register_region(base, base + 3,
            [base](uint32_t address) -> uint32_t {
                if (address != base || !experimentExiTransfer.sramAllowed) {
                    throw std::runtime_error("SRAM DMA register read unverified");
                }
                return base == 0xcd006804 ? experimentExiTransfer.dmaAddress : experimentExiTransfer.dmaLength;
            },
            [base](uint32_t address, uint32_t value) {
                auto& transfer = experimentExiTransfer;
                if (address != base || !transfer.sramAllowed || (experimentExiMaskState[0] & 0x3f0) != 0x130
                    || transfer.phase != 1 || !transfer.command || transfer.data != 0x20000100
                    || (base == 0xcd006804 ? value != 0x80492600 : value != 64 || transfer.dmaAddress != 0x80492600)) {
                    throw std::runtime_error("SRAM DMA register write unverified");
                }
                (base == 0xcd006804 ? transfer.dmaAddress : transfer.dmaLength) = value;
            },
            [](uint32_t) -> uint16_t { throw std::runtime_error("SRAM DMA halfword read unverified"); },
            [](uint32_t, uint16_t) { throw std::runtime_error("SRAM DMA halfword write unverified"); });
    }
    for (unsigned channel = 1; channel < 3; ++channel) {
        const uint32_t base = 0xcd00680c + channel * 20;
        dispatcher.register_region(base, base + 3,
            [base](uint32_t address) -> uint32_t {
                if (address != base) {
                    throw std::runtime_error("GetID idle control alignment unverified");
                }
                return 0;
            },
            [](uint32_t, uint32_t) { throw std::runtime_error("GetID other channel transfer unverified"); },
            [](uint32_t) -> uint16_t { throw std::runtime_error("GetID idle halfword unverified"); },
            [](uint32_t, uint16_t) { throw std::runtime_error("GetID idle halfword unverified"); });
    }
    dispatcher.register_region(0xcd006024, 0xcd006027,
        [](uint32_t address) -> uint32_t {
            if (address != 0xcd006024) {
                throw std::runtime_error("GetID DI config alignment unverified");
            }
            return 1;
        },
        [](uint32_t, uint32_t) { throw std::runtime_error("GetID DI config is read only"); },
        [](uint32_t) -> uint16_t { throw std::runtime_error("GetID DI config halfword unverified"); },
        [](uint32_t, uint16_t) { throw std::runtime_error("GetID DI config halfword unverified"); });
    dispatcher.register_region(0xcd00680c, 0xcd00680f,
        [](uint32_t address) -> uint32_t {
            if (address != 0xcd00680c) {
                throw std::runtime_error("GetID control alignment unverified");
            }
            return experimentExiTransfer.control;
        },
        [](uint32_t address, uint32_t value) {
            auto& transfer = experimentExiTransfer;
            if (address == 0xcd00680c && transfer.sramAllowed && (experimentExiMaskState[0] & 0x3f0) == 0x130) {
                const bool command = transfer.phase == 0 && transfer.command && transfer.data == 0x20000100 && value == 0x35;
                const bool dma = transfer.phase == 1 && transfer.command && transfer.data == 0x20000100 && value == 3
                    && transfer.dmaAddress == 0x80492600 && transfer.dmaLength == 64 && transfer.dmaWrite;
                if (!command && !dma) {
                    throw std::runtime_error("SRAM transfer outside measured command/DMA protocol");
                }
                const bool lost = transfer.loseCompletion || (dma && transfer.loseDmaCompletion);
                if (dma && !lost) {
                    auto response = transfer.sramResponse;
                    if (transfer.wrongResponse) {
                        response[0] ^= 1;
                    }
                    transfer.dmaWrite(transfer.dmaAddress & 0x1fffffffu, response);
                }
                transfer.control = lost ? value : value & ~1u;
                if (!lost) {
                    experimentExiMaskState[0] |= 8;
                    experiment_getid_update_pi();
                    ++transfer.phase;
                }
                transfer.observations.push_back({value, transfer.control, experimentExiMaskState[0], transfer.data});
                return;
            }
            if (address == 0xcd00680c && transfer.uartAllowed && (experimentExiMaskState[0] & 0x3f0) == 0x140) {
                const bool command = transfer.phase == 0 && transfer.command && value == 0x35
                    && (transfer.data == 0xb0000000 || transfer.data == 0xb0000100 || transfer.data == 0x30000100);
                const bool queueRead = transfer.phase == 1 && transfer.uartCommand == 0x30000100 && value == 0x31;
                const bool config = transfer.phase == 1 && transfer.uartCommand == 0xb0000000 && value == 0x35
                    && (transfer.data == 0xf2000000 || transfer.data == 0xf3000000);
                const bool payload = transfer.phase >= 1 && transfer.uartCommand == 0xb0000100 && value == 0x35 && !(transfer.data & 0xffffff);
                if (!command && !queueRead && !config && !payload) {
                    throw std::runtime_error("UART transfer outside measured protocol");
                }
                transfer.control = transfer.loseCompletion ? value : value & ~1u;
                if (!transfer.loseCompletion) {
                    if (command) {
                        transfer.uartCommand = transfer.data;
                    } else if (queueRead) {
                        transfer.data = transfer.wrongResponse ? 0x20000000 : 0;
                    } else if (payload) {
                        transfer.uartBytes.push_back(transfer.data >> 24);
                    }
                    experimentExiMaskState[0] |= 8;
                    experiment_getid_update_pi();
                    ++transfer.phase;
                }
                transfer.observations.push_back({value, transfer.control, experimentExiMaskState[0], transfer.data});
                return;
            }
            if (address != 0xcd00680c || (experimentExiMaskState[0] & 0x380) != 0x200
                || (transfer.phase == 0 && (value != 0x15 || !transfer.command || transfer.data))
                || (transfer.phase == 1 && value != 0x31) || transfer.phase > 1) {
                throw std::runtime_error("GetID transfer outside measured None device transaction");
            }
            transfer.control = transfer.loseCompletion ? value : value & ~1u;
            if (!transfer.loseCompletion) {
                if (transfer.phase == 1) {
                    transfer.data = transfer.wrongResponse ? 1 : 0;
                }
                experimentExiMaskState[0] |= 8;
                experiment_getid_update_pi();
                ++transfer.phase;
            }
            transfer.observations.push_back({value, transfer.control, experimentExiMaskState[0], transfer.data});
        },
        [](uint32_t) -> uint16_t { throw std::runtime_error("GetID halfword control unverified"); },
        [](uint32_t, uint16_t) { throw std::runtime_error("GetID halfword control unverified"); });
    dispatcher.register_region(0xcd006810, 0xcd006813,
        [](uint32_t address) -> uint32_t {
            if (address != 0xcd006810) {
                throw std::runtime_error("GetID data alignment unverified");
            }
            return experimentExiTransfer.data;
        },
        [](uint32_t address, uint32_t value) {
            auto& transfer = experimentExiTransfer;
            if (address == 0xcd006810 && transfer.sramAllowed && (experimentExiMaskState[0] & 0x3f0) == 0x130) {
                if (transfer.phase || transfer.command || value != 0x20000100) {
                    throw std::runtime_error("SRAM command outside measured protocol");
                }
                transfer.data = value;
                transfer.command = true;
                return;
            }
            if (address == 0xcd006810 && transfer.uartAllowed && (experimentExiMaskState[0] & 0x3f0) == 0x140) {
                const bool command = transfer.phase == 0 && !transfer.command
                    && (value == 0xb0000000 || value == 0xb0000100 || value == 0x30000100);
                const bool config = transfer.phase == 1 && transfer.uartCommand == 0xb0000000
                    && (value == 0xf2000000 || value == 0xf3000000);
                const bool payload = transfer.phase >= 1 && transfer.uartCommand == 0xb0000100 && !(value & 0xffffff);
                if (!command && !config && !payload) {
                    throw std::runtime_error("UART data outside measured protocol");
                }
                transfer.data = value;
                transfer.command = true;
                return;
            }
            if (address != 0xcd006810 || value || experimentExiTransfer.phase || experimentExiTransfer.command) {
                throw std::runtime_error("GetID command outside measured profile");
            }
            experimentExiTransfer.data = value;
            experimentExiTransfer.command = true;
        },
        [](uint32_t) -> uint16_t { throw std::runtime_error("GetID halfword data unverified"); },
        [](uint32_t, uint16_t) { throw std::runtime_error("GetID halfword data unverified"); });
}
}
