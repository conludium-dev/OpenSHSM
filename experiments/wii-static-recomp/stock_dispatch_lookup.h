#pragma once
#include <cstddef>
#include <cstdint>

namespace nwii::runtime { struct CPUContext; }

struct StockDispatchRoute {
    uint32_t address;
    void (*function)(nwii::runtime::CPUContext&);
};

extern "C" size_t stock_dispatch_index(const StockDispatchRoute* routes, size_t count, uint32_t target);
