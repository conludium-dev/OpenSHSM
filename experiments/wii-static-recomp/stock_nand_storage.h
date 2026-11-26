#pragma once
#include "stock_nand_snapshot.h"
#include <cerrno>
#include <cstdlib>
#include <cstdio>
#include <filesystem>
#include <optional>
#ifndef _WIN32
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace openshsm::experiment {
class NandCommitUncertain : public std::runtime_error {
public:
    NandCommitUncertain() : std::runtime_error("NAND replaced but directory sync failed; saving disabled") {}
};

inline std::filesystem::path nand_user_directory() {
    std::filesystem::path base;
    if (const char* configured = std::getenv("OPENSHSM_USER_DATA")) {
        base = configured;
    } else {
#ifdef _WIN32
        const char* location = std::getenv("LOCALAPPDATA");
        if (!location) {
            throw std::runtime_error("LOCALAPPDATA unavailable for persistent saves");
        }
        base = std::filesystem::path(location) / "OpenSHSM";
#elif defined(__APPLE__)
        const char* location = std::getenv("HOME");
        if (!location) {
            throw std::runtime_error("User home unavailable for persistent saves");
        }
        base = std::filesystem::path(location) / "Library/Application Support/OpenSHSM";
#else
        if (const char* location = std::getenv("XDG_DATA_HOME")) {
            base = std::filesystem::path(location) / "OpenSHSM";
        } else if (const char* location = std::getenv("HOME")) {
            base = std::filesystem::path(location) / ".local/share/OpenSHSM";
        } else {
            throw std::runtime_error("User data directory unavailable for persistent saves");
        }
#endif
    }
    if (!base.is_absolute()) {
        throw std::runtime_error("Persistent save directory must be absolute");
    }
    return base / "nand/R5WEA4";
}

class NandStorage {
    int directory_ = -1;
    int lock_ = -1;
    bool mounted_ = false;
    bool blocked_ = false;
    unsigned sequence_ = 0;

    std::optional<std::vector<uint8_t>> read_snapshot() {
#ifdef _WIN32
        throw std::runtime_error("Persistent NAND Windows storage is not implemented");
#else
        const int fd = ::openat(directory_, "nand.bin", O_RDONLY | O_NOFOLLOW);
        if (fd < 0) {
            if (errno == ENOENT) {
                return std::nullopt;
            }
            throw std::runtime_error("Cannot open persistent NAND snapshot");
        }
        struct stat status{};
        if (::fstat(fd, &status) != 0 || !S_ISREG(status.st_mode) || status.st_size < 0 ||
                static_cast<uint64_t>(status.st_size) > nand_snapshot_limit + 24) {
            ::close(fd);
            throw std::runtime_error("Invalid persistent NAND snapshot file");
        }
        std::vector<uint8_t> data(static_cast<size_t>(status.st_size));
        size_t offset = 0;
        while (offset < data.size()) {
            const auto read = ::read(fd, data.data() + offset, data.size() - offset);
            if (read < 0 && errno == EINTR) {
                continue;
            }
            if (read <= 0) {
                ::close(fd);
                throw std::runtime_error("Cannot read complete persistent NAND snapshot");
            }
            offset += static_cast<size_t>(read);
        }
        ::close(fd);
        return data;
#endif
    }

    void commit(const std::vector<uint8_t>& data) {
#ifdef _WIN32
        throw std::runtime_error("Persistent NAND Windows storage is not implemented");
#else
        if (!mounted_ || blocked_ || data.size() > nand_snapshot_limit + 24) {
            throw std::runtime_error("Persistent NAND saving disabled or snapshot too large");
        }
        struct stat target{};
        if (::fstatat(directory_, "nand.bin", &target, AT_SYMLINK_NOFOLLOW) == 0) {
            if (!S_ISREG(target.st_mode)) {
                throw std::runtime_error("Persistent NAND target is not a regular file");
            }
        } else if (errno != ENOENT) {
            throw std::runtime_error("Cannot inspect persistent NAND target");
        }
        const std::string stage = "nand.bin.pending." + std::to_string(::getpid()) + '.' + std::to_string(sequence_++);
        const int fd = ::openat(directory_, stage.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
        if (fd < 0) {
            throw std::runtime_error("Cannot create persistent NAND staged file");
        }
        size_t offset = 0;
        bool okay = true;
        while (offset < data.size()) {
            const auto written = ::write(fd, data.data() + offset, data.size() - offset);
            if (written < 0 && errno == EINTR) {
                continue;
            }
            if (written <= 0) {
                okay = false;
                break;
            }
            offset += static_cast<size_t>(written);
        }
        okay = okay && ::fsync(fd) == 0;
        if (::close(fd) != 0) {
            okay = false;
        }
        if (!okay || ::renameat(directory_, stage.c_str(), directory_, "nand.bin") != 0) {
            ::unlinkat(directory_, stage.c_str(), 0);
            throw std::runtime_error("Persistent NAND commit failed before replacement");
        }
        if (::fsync(directory_) != 0) {
            blocked_ = true;
            throw NandCommitUncertain();
        }
#endif
    }

public:
    explicit NandStorage(const std::filesystem::path& directory) {
#ifdef _WIN32
        throw std::runtime_error("Persistent NAND Windows storage is not implemented");
#else
        if (!directory.is_absolute() || directory == directory.root_path()) {
            throw std::runtime_error("Invalid persistent NAND directory");
        }
        std::filesystem::path inspected;
        for (const auto& component : directory) {
            if (component == "..") {
                throw std::runtime_error("Persistent NAND directory traversal refused");
            }
            inspected /= component;
            std::error_code error;
            const auto status = std::filesystem::symlink_status(inspected, error);
            if (std::filesystem::is_symlink(status) || (error && error != std::errc::no_such_file_or_directory)) {
                throw std::runtime_error("Persistent NAND symlink or inaccessible directory refused");
            }
        }
        const bool created = std::filesystem::create_directories(directory);
        if (created && ::chmod(directory.c_str(), 0700) != 0) {
            throw std::runtime_error("Cannot set persistent NAND directory permissions");
        }
        directory_ = ::open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
        if (directory_ < 0) {
            throw std::runtime_error("Cannot open persistent NAND directory");
        }
        lock_ = ::openat(directory_, "nand.lock", O_RDWR | O_CREAT | O_NOFOLLOW, 0600);
        if (lock_ < 0 || ::flock(lock_, LOCK_EX | LOCK_NB) != 0) {
            if (lock_ >= 0) {
                ::close(lock_);
            }
            ::close(directory_);
            lock_ = directory_ = -1;
            throw std::runtime_error("Persistent NAND is locked or lock file unavailable");
        }
#endif
    }

    NandStorage(const NandStorage&) = delete;
    NandStorage& operator=(const NandStorage&) = delete;
    ~NandStorage() {
#ifndef _WIN32
        if (lock_ >= 0) {
            ::close(lock_);
        }
        if (directory_ >= 0) {
            ::close(directory_);
        }
#endif
    }

    template<class Node>
    void load(std::vector<Node>& registry, const std::string& title) {
        if (mounted_ || blocked_) {
            throw std::runtime_error("Persistent NAND mount already used or blocked");
        }
        try {
            if (const auto data = read_snapshot()) {
                nand_decode_snapshot(*data, registry, title);
            }
            mounted_ = true;
        } catch (...) {
            blocked_ = true;
            throw;
        }
    }

    template<class Node>
    void save(const std::vector<Node>& registry, const std::string& title) {
        commit(nand_encode_snapshot(registry, title));
    }
};
}
