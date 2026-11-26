#pragma once
#include <algorithm>
#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace openshsm::experiment {
inline constexpr size_t nand_snapshot_limit = 16 * 1024 * 1024;

inline uint32_t nand_crc32(const std::vector<uint8_t>& data, size_t begin) {
    uint32_t crc = 0xffffffffu;
    for (size_t i = begin; i < data.size(); ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit) {
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
        }
    }
    return ~crc;
}

inline bool nand_saved_path(const std::string& path, const std::string& title) {
    return path == title || path.starts_with(title + '/');
}

inline bool nand_snapshot_path(const std::string& path, const std::string& title) {
    if (title.empty() || path.empty() || !nand_saved_path(path, title) || path.size() >= 64 || path.back() == '/' ||
            path.find("..") != std::string::npos || path.find("//") != std::string::npos) {
        return false;
    }
    return std::all_of(path.begin(), path.end(), [](unsigned char c) { return c >= 0x20 && c <= 0x7e; });
}

inline void nand_put32(std::vector<uint8_t>& data, uint32_t value) {
    for (unsigned shift = 0; shift < 32; shift += 8) {
        data.push_back(static_cast<uint8_t>(value >> shift));
    }
}

inline uint32_t nand_get32(const std::vector<uint8_t>& data, size_t& offset) {
    if (offset > data.size() || data.size() - offset < 4) {
        throw std::runtime_error("Truncated persistent NAND snapshot");
    }
    uint32_t value = 0;
    for (unsigned shift = 0; shift < 32; shift += 8) {
        value |= uint32_t(data[offset++]) << shift;
    }
    return value;
}

template<class Node>
inline void nand_validate_nodes(const std::vector<Node>& nodes, const std::string& title) {
    std::map<std::string, bool> paths;
    size_t bytes = 0;
    for (const auto& node : nodes) {
        if (!nand_snapshot_path(node.path, title) || !paths.emplace(node.path, node.is_directory).second ||
                (node.is_directory && !node.data.empty()) || node.data.size() > nand_snapshot_limit ||
                !std::all_of(std::begin(node.modes), std::end(node.modes), [](uint8_t mode) { return mode <= 3; })) {
            throw std::runtime_error("Invalid persistent NAND node");
        }
        bytes += node.data.size() + node.path.size() + 40;
        if (bytes > nand_snapshot_limit || paths.size() > 1024) {
            throw std::runtime_error("Persistent NAND snapshot limit exceeded");
        }
    }
    if (!paths.contains(title) || !paths.at(title)) {
        throw std::runtime_error("Persistent NAND title directory missing");
    }
    for (const auto& [path, directory] : paths) {
        if (path != title) {
            const auto parent = path.substr(0, path.rfind('/'));
            if (!paths.contains(parent) || !paths.at(parent)) {
                throw std::runtime_error("Persistent NAND node parent missing");
            }
        }
    }
}

template<class Node>
inline std::vector<uint8_t> nand_encode_snapshot(const std::vector<Node>& registry, const std::string& title) {
    std::vector<Node> saved;
    for (const auto& node : registry) {
        if (nand_saved_path(node.path, title)) {
            saved.push_back(node);
        }
    }
    nand_validate_nodes(saved, title);
    std::vector<uint8_t> data{'S', 'H', 'S', 'M', 'N', 'N', 'D', '1'};
    nand_put32(data, 1);
    nand_put32(data, static_cast<uint32_t>(saved.size()));
    nand_put32(data, 0);
    nand_put32(data, 0);
    for (const auto& node : saved) {
        nand_put32(data, static_cast<uint32_t>(node.path.size()));
        nand_put32(data, node.is_directory);
        nand_put32(data, node.uid);
        nand_put32(data, node.gid);
        for (uint8_t mode : node.modes) {
            nand_put32(data, mode);
        }
        nand_put32(data, node.attribute);
        nand_put32(data, static_cast<uint32_t>(node.data.size()));
        data.insert(data.end(), node.path.begin(), node.path.end());
        data.insert(data.end(), node.data.begin(), node.data.end());
    }
    const uint32_t size = static_cast<uint32_t>(data.size() - 24);
    const uint32_t crc = nand_crc32(data, 24);
    for (unsigned i = 0; i < 4; ++i) {
        data[16 + i] = static_cast<uint8_t>(size >> (i * 8));
        data[20 + i] = static_cast<uint8_t>(crc >> (i * 8));
    }
    return data;
}

template<class Node>
inline void nand_decode_snapshot(const std::vector<uint8_t>& data, std::vector<Node>& registry,
        const std::string& title) {
    constexpr uint8_t magic[] = {'S', 'H', 'S', 'M', 'N', 'N', 'D', '1'};
    if (data.size() < 24 || data.size() > nand_snapshot_limit + 24 ||
            !std::equal(std::begin(magic), std::end(magic), data.begin())) {
        throw std::runtime_error("Invalid persistent NAND snapshot header");
    }
    size_t offset = 8;
    const uint32_t version = nand_get32(data, offset);
    const uint32_t count = nand_get32(data, offset);
    const uint32_t size = nand_get32(data, offset);
    const uint32_t crc = nand_get32(data, offset);
    if (version != 1 || count == 0 || count > 1024 || size != data.size() - 24 || crc != nand_crc32(data, 24)) {
        throw std::runtime_error("Corrupt or unsupported persistent NAND snapshot");
    }
    std::vector<Node> loaded;
    for (uint32_t index = 0; index < count; ++index) {
        Node node{};
        const uint32_t path_size = nand_get32(data, offset);
        const uint32_t directory = nand_get32(data, offset);
        node.uid = nand_get32(data, offset);
        const uint32_t gid = nand_get32(data, offset);
        uint32_t modes[3];
        for (auto& mode : modes) {
            mode = nand_get32(data, offset);
        }
        const uint32_t attribute = nand_get32(data, offset);
        const uint32_t bytes = nand_get32(data, offset);
        if (path_size == 0 || path_size >= 64 || directory > 1 || gid > 65535 || attribute > 255 ||
                modes[0] > 3 || modes[1] > 3 || modes[2] > 3 || offset > data.size() ||
                uint64_t(path_size) + bytes > data.size() - offset) {
            throw std::runtime_error("Invalid persistent NAND node size or attributes");
        }
        node.path.assign(reinterpret_cast<const char*>(data.data() + offset), path_size);
        offset += path_size;
        node.data.assign(data.begin() + offset, data.begin() + offset + bytes);
        offset += bytes;
        node.is_directory = directory != 0;
        node.gid = static_cast<uint16_t>(gid);
        node.attribute = static_cast<uint8_t>(attribute);
        for (unsigned i = 0; i < 3; ++i) {
            node.modes[i] = static_cast<uint8_t>(modes[i]);
        }
        loaded.push_back(std::move(node));
    }
    if (offset != data.size()) {
        throw std::runtime_error("Trailing persistent NAND snapshot data");
    }
    nand_validate_nodes(loaded, title);
    std::vector<Node> merged;
    for (const auto& node : registry) {
        if (!nand_saved_path(node.path, title)) {
            merged.push_back(node);
        }
    }
    merged.insert(merged.end(), loaded.begin(), loaded.end());
    registry.swap(merged);
}
}
