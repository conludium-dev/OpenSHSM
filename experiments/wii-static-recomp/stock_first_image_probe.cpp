#include "stock_first_image.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

int main(int argc, char** argv) {
    openshsm::experiment::FirstImageGate gate;
    for (int i = 1; i < argc; ++i) {
        std::ifstream file(argv[i], std::ios::binary);
        std::vector<uint8_t> bmp((std::istreambuf_iterator<char>(file)), {});
        if (bmp.size() < 54 || bmp[0] != 'B' || bmp[1] != 'M' || bmp[28] != 32 || bmp[29] != 0) {
            return 2;
        }
        uint32_t offset = uint32_t(bmp[10]) | (uint32_t(bmp[11]) << 8) |
            (uint32_t(bmp[12]) << 16) | (uint32_t(bmp[13]) << 24);
        if (offset > bmp.size()) {
            return 3;
        }
        std::cout << argv[i] << " visible=" << gate.observe(bmp.data() + offset, bmp.size() - offset) << '\n';
    }
    return 0;
}
