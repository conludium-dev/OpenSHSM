#include "bat_translation.h"
#include <iostream>

int main() {
    uint32_t hid4, msr, address, instruction;
    while (std::cin >> hid4 >> msr >> address >> instruction) {
        std::array<nwii::runtime::BatPair, 8> bank{};
        for (auto& pair : bank) {
            if (!(std::cin >> pair.upper >> pair.lower)) {
                return 8;
            }
        }
        try {
            const auto result = nwii::runtime::resolve_reference_bat(bank, hid4, msr, address, instruction != 0);
            std::cout << result.physical << ' ' << result.wimg << ' ' << result.slot << '\n';
        } catch (const std::runtime_error&) {
            std::cout << "REFUSED\n";
        }
    }
    return std::cin.eof() ? 0 : 8;
}
