#pragma once
#include "stock_loading_observation.h"

namespace stock_loading_observation {
inline void capture_payload(nwii::runtime::CPUContext& ctx) {
    const char* prefix = std::getenv("NWII_THPDUMP");
    static unsigned serial = 0;
    if (!prefix || serial >= 16) {
        return;
    }
    const unsigned id = serial++;
    const uint32_t address = ctx.gpr[5], size = ctx.gpr[6];
    const uint64_t end = uint64_t(address) + size;
    if (!size || size > 1024 * 1024 || !((address >= 0x80004000 && end <= 0x81800000)
        || (address >= 0x90000000 && end <= 0x94000000))) {
        return;
    }
    const uint8_t* data = ctx.mmu.get_ptr(address);
    if (!data) {
        return;
    }
    const std::string path = std::string(prefix) + "-payload" + std::to_string(id) + ".bin";
    std::ofstream file(path, std::ios::binary);
    if (!file) {
        return;
    }
    file.write(reinterpret_cast<const char*>(data), size);
    file.close();
    if (!file) {
        return;
    }
    std::ofstream metadata(std::string(prefix) + "-payloads.jsonl", std::ios::app);
    metadata << "{\"id\":" << id << ",\"address\":" << address << ",\"size\":" << size
        << ",\"request\":" << ctx.gpr[31] << ",\"callback\":" << ctx.ctr << "}\n";
}
}
