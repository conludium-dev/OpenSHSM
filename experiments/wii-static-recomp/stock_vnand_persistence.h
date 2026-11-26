#pragma once

static bool g_vnand_persist_readonly = false;
static constexpr const char *k_vnand_title_data = "/title/00010000/52355745/data/";

static std::filesystem::path vnand_save_path() {
    if (nwii::runtime::Config::get().game_id != "R5WEA4") {
        return {};
    }
    const char *override_dir = std::getenv("OPENSHSM_SAVE_DIR");
    const std::filesystem::path root = override_dir && override_dir[0] ? override_dir : "saves";
    return root / "R5WEA4" / "vnand-v1.bin";
}

static void vnand_put(std::vector<uint8_t>& bytes, uint64_t value, unsigned width) {
    for (unsigned i = 0; i < width; ++i) {
        bytes.push_back(uint8_t(value >> (8 * i)));
    }
}

static bool vnand_get(const std::vector<uint8_t>& bytes, size_t& offset,
        size_t end, unsigned width, uint64_t& value) {
    if (width > end || offset > end - width) {
        return false;
    }
    value = 0;
    for (unsigned i = 0; i < width; ++i) {
        value |= uint64_t(bytes[offset++]) << (8 * i);
    }
    return true;
}

static uint64_t vnand_checksum(const std::vector<uint8_t>& bytes, size_t end) {
    uint64_t value = 14695981039346656037ull;
    for (size_t i = 0; i < end; ++i) {
        value = (value ^ bytes[i]) * 1099511628211ull;
    }
    return value;
}

static bool vnand_persist() {
    const auto path = vnand_save_path();
    if (path.empty()) {
        return true;
    }
    if (g_vnand_persist_readonly) {
        return false;
    }
    std::vector<const VNandFile *> files;
    size_t total = 0;
    for (const auto& file : g_vnand_files) {
        if (!file.path.starts_with(k_vnand_title_data)) {
            continue;
        }
        if (file.path.size() >= 64 || file.data.size() > 16 * 1024 * 1024
            || total > 64 * 1024 * 1024 - file.data.size() || files.size() >= 32) {
            return false;
        }
        files.push_back(&file);
        total += file.data.size();
    }
    std::vector<uint8_t> bytes{'O', 'S', 'V', 'N', '0', '0', '0', '1'};
    vnand_put(bytes, files.size(), 4);
    for (const VNandFile *file : files) {
        vnand_put(bytes, file->path.size(), 1);
        bytes.insert(bytes.end(), file->path.begin(), file->path.end());
        vnand_put(bytes, file->is_directory, 1);
        vnand_put(bytes, file->uid, 4);
        vnand_put(bytes, file->gid, 2);
        for (const uint8_t mode : file->modes) {
            vnand_put(bytes, mode, 1);
        }
        vnand_put(bytes, file->attribute, 1);
        vnand_put(bytes, file->data.size(), 4);
        bytes.insert(bytes.end(), file->data.begin(), file->data.end());
    }
    vnand_put(bytes, vnand_checksum(bytes, bytes.size()), 8);
    std::error_code error;
    std::filesystem::create_directories(path.parent_path(), error);
    if (error) {
        return false;
    }
    std::filesystem::permissions(path.parent_path(),
        std::filesystem::perms::owner_all, std::filesystem::perm_options::replace, error);
    if (error) {
        return false;
    }
    auto temporary = path;
    temporary += ".tmp";
    {
        std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
        if (!output) {
            return false;
        }
        std::filesystem::permissions(temporary,
            std::filesystem::perms::owner_read | std::filesystem::perms::owner_write,
            std::filesystem::perm_options::replace, error);
        if (error || !output.write(reinterpret_cast<const char *>(bytes.data()), bytes.size())) {
            return false;
        }
        output.flush();
        if (!output) {
            return false;
        }
    }
    std::filesystem::rename(temporary, path, error);
    return !error;
}

static bool vnand_restore() {
    const auto path = vnand_save_path();
    if (path.empty()) {
        return true;
    }
    std::error_code error;
    if (!std::filesystem::exists(path, error)) {
        g_vnand_persist_readonly = bool(error);
        return !error;
    }
    if (std::filesystem::is_symlink(path, error) || error) {
        g_vnand_persist_readonly = true;
        return false;
    }
    const auto size = std::filesystem::file_size(path, error);
    if (error || size < 20 || size > 64 * 1024 * 1024) {
        g_vnand_persist_readonly = true;
        return false;
    }
    std::ifstream input(path, std::ios::binary);
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)), {});
    if (input.bad() || bytes.size() != size
        || !std::equal(bytes.begin(), bytes.begin() + 8, "OSVN0001")) {
        g_vnand_persist_readonly = true;
        return false;
    }
    size_t offset = 8;
    const size_t end = bytes.size() - 8;
    size_t checksum_offset = end;
    uint64_t count = 0, expected = 0;
    if (!vnand_get(bytes, offset, end, 4, count) || count > 32
        || !vnand_get(bytes, checksum_offset, bytes.size(), 8, expected)
        || expected != vnand_checksum(bytes, bytes.size() - 8)) {
        g_vnand_persist_readonly = true;
        return false;
    }
    std::vector<VNandFile> restored;
    for (uint64_t i = 0; i < count; ++i) {
        uint64_t name_size = 0, directory = 0, uid = 0, gid = 0, attribute = 0, data_size = 0;
        if (!vnand_get(bytes, offset, bytes.size() - 8, 1, name_size)
            || name_size == 0 || name_size >= 64 || offset + name_size > bytes.size() - 8) {
            g_vnand_persist_readonly = true;
            return false;
        }
        VNandFile file;
        file.path.assign(reinterpret_cast<const char *>(bytes.data() + offset), name_size);
        offset += name_size;
        if (!file.path.starts_with(k_vnand_title_data) || file.path.find("..") != std::string::npos
            || file.path.find("//") != std::string::npos
            || std::any_of(restored.begin(), restored.end(), [&](const VNandFile& other) {
                return other.path == file.path;
            }) || !vnand_get(bytes, offset, bytes.size() - 8, 1, directory)
            || directory > 1 || !vnand_get(bytes, offset, bytes.size() - 8, 4, uid)
            || !vnand_get(bytes, offset, bytes.size() - 8, 2, gid)) {
            g_vnand_persist_readonly = true;
            return false;
        }
        file.is_directory = directory != 0;
        file.uid = uint32_t(uid);
        file.gid = uint16_t(gid);
        for (uint8_t& mode : file.modes) {
            uint64_t value = 0;
            if (!vnand_get(bytes, offset, bytes.size() - 8, 1, value) || value > 3) {
                g_vnand_persist_readonly = true;
                return false;
            }
            mode = uint8_t(value);
        }
        if (!vnand_get(bytes, offset, bytes.size() - 8, 1, attribute)
            || !vnand_get(bytes, offset, bytes.size() - 8, 4, data_size)
            || data_size > 16 * 1024 * 1024 || data_size > bytes.size() - 8 - offset
            || (file.is_directory && data_size != 0)) {
            g_vnand_persist_readonly = true;
            return false;
        }
        file.attribute = uint8_t(attribute);
        file.data.assign(bytes.begin() + offset, bytes.begin() + offset + data_size);
        offset += data_size;
        restored.push_back(std::move(file));
    }
    if (offset != bytes.size() - 8) {
        g_vnand_persist_readonly = true;
        return false;
    }
    std::filesystem::permissions(path.parent_path(),
        std::filesystem::perms::owner_all, std::filesystem::perm_options::replace, error);
    if (!error) {
        std::filesystem::permissions(path,
            std::filesystem::perms::owner_read | std::filesystem::perms::owner_write,
            std::filesystem::perm_options::replace, error);
    }
    if (error) {
        g_vnand_persist_readonly = true;
        return false;
    }
    g_vnand_files.insert(g_vnand_files.end(),
        std::make_move_iterator(restored.begin()), std::make_move_iterator(restored.end()));
    return true;
}
