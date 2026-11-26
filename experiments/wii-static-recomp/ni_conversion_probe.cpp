#include "ni_conversion.h"
#include <iostream>

int main() {
    uint64_t value;
    unsigned ni;
    while (std::cin >> value >> ni) {
        if (ni > 1) {
            return 8;
        }
        try {
            const auto result = nwii::runtime::ni_single_nearest_bits(value, ni != 0);
            std::cout << result << ' ' << nwii::runtime::widen_single_bits(result) << '\n';
        } catch (const std::runtime_error&) {
            std::cout << "REFUSED\n";
        }
    }
    return std::cin.eof() ? 0 : 8;
}
