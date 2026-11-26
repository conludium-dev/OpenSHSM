#pragma once
#include <cstdint>

namespace nwii::analyzer {
bool experimentFunctionContains(uint32_t entry, uint32_t address);
uint32_t experimentJumpTableLimit(uint32_t base);
}
