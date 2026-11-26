#include "stock_nand_storage.h"
#include <cstdio>
#include <fstream>
#include <iterator>
#include <thread>
#include <chrono>

struct TestNode {
    std::string path;
    std::vector<uint8_t> data;
    bool is_directory = false;
    uint32_t uid = 0;
    uint16_t gid = 0;
    uint8_t modes[3] = {3, 3, 3};
    uint8_t attribute = 0;
};

static const std::string title = "/title/00010000/52355745/data";
static std::vector<TestNode> initial() {
    return {{"/shared2/sys/SYSCONF", {9, 8}}, {title, {}, true}, {"/tmp/Store.tmp", {7}}};
}

static std::vector<uint8_t> read(const std::filesystem::path& file) {
    std::ifstream stream(file, std::ios::binary);
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}

int main(int argc, char** argv) {
    using namespace openshsm::experiment;
    if (argc != 3) {
        return 2;
    }
    const std::string mode = argv[1];
    const std::filesystem::path directory = argv[2];
    auto registry = initial();
    if (mode == "write") {
        NandStorage store(directory);
        store.load(registry, title);
        registry.push_back({title + "/Store.000", {0, 1, 0xff, 4, 5}, false, 0x12345678, 42, {1, 2, 3}, 7});
        store.save(registry, title);
        std::puts("SYNTHETIC_NAND_DURABLE_WRITE");
        std::fflush(stdout);
        std::_Exit(0);
    }
    if (mode == "read") {
        NandStorage store(directory);
        store.load(registry, title);
        const auto found = std::find_if(registry.begin(), registry.end(), [](const auto& node) {
            return node.path == title + "/Store.000";
        });
        if (found == registry.end() || found->data != std::vector<uint8_t>({0, 1, 0xff, 4, 5}) ||
                found->uid != 0x12345678 || found->gid != 42 || found->attribute != 7 ||
                found->modes[0] != 1 || found->modes[1] != 2 || found->modes[2] != 3 ||
                registry.front().data != std::vector<uint8_t>({9, 8})) {
            return 3;
        }
        std::puts("SYNTHETIC_NAND_FRESH_PROCESS_RELOAD");
        return 0;
    }
    if (mode == "hold") {
        NandStorage store(directory);
        store.load(registry, title);
        std::puts("LOCKED");
        std::fflush(stdout);
        std::this_thread::sleep_for(std::chrono::seconds(15));
        return 0;
    }
    if (mode == "locked") {
        try {
            NandStorage store(directory);
        } catch (const std::runtime_error&) {
            std::puts("SECOND_WRITER_REFUSED");
            return 0;
        }
        return 4;
    }
    if (mode != "contracts") {
        return 5;
    }
    unsigned cases = 0;
    registry.push_back({title + "/Store.000", {0, 1, 0xff, 4, 5}, false, 19, 42, {1, 2, 3}, 7});
    const auto encoded = nand_encode_snapshot(registry, title);
    for (size_t index = 0; index < encoded.size(); ++index) {
        for (unsigned bit = 0; bit < 8; ++bit) {
            auto corrupted = encoded;
            corrupted[index] ^= 1u << bit;
            auto retained = initial();
            const auto previous = nand_encode_snapshot(retained, title);
            try {
                nand_decode_snapshot(corrupted, retained, title);
                return 6;
            } catch (const std::runtime_error&) {
                if (nand_encode_snapshot(retained, title) != previous) {
                    return 7;
                }
                ++cases;
            }
        }
    }
    for (size_t size = 0; size < encoded.size(); ++size) {
        auto truncated = encoded;
        truncated.resize(size);
        try {
            auto retained = initial();
            nand_decode_snapshot(truncated, retained, title);
            return 8;
        } catch (const std::runtime_error&) {
            ++cases;
        }
    }
    for (std::string bad : {title + "/../bad", title + "//bad", title + "/missing/Store.000", title + "/"}) {
        auto invalid = registry;
        invalid.push_back({bad, {1}});
        try {
            nand_encode_snapshot(invalid, title);
            return 9;
        } catch (const std::runtime_error&) {
            ++cases;
        }
    }
    NandStorage store(directory);
    auto mounted = initial();
    store.load(mounted, title);
    store.save(registry, title);
    const auto before = read(directory / "nand.bin");
    auto invalid = registry;
    invalid.back().data.resize(nand_snapshot_limit + 1);
    try {
        store.save(invalid, title);
        return 10;
    } catch (const std::runtime_error&) {
        if (read(directory / "nand.bin") != before) {
            return 11;
        }
        ++cases;
    }
    std::printf("NAND_STORAGE_COMPONENT_PASS %u malformed/limit cases; previous snapshot retained\n", cases);
}
