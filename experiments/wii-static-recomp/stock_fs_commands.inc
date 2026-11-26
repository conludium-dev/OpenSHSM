    static uint32_t fs_virtual(uint32_t address) {
        if (address < 0x01800000 || (address >= 0x10000000 && address < 0x14000000)) {
            return address | 0x80000000;
        }
        return address;
    }

    static bool fs_span(uint32_t address, uint32_t size) {
        const uint64_t start = fs_virtual(address), end = start + size;
        return (start >= 0x80004000 && end <= 0x81800000)
            || (start >= 0x90000000 && end <= 0x94000000);
    }

    static bool fs_path(CPUContext& ctx, uint32_t address, std::string& path) {
        if (!fs_span(address, 64)) {
            return false;
        }
        path.clear();
        for (unsigned i = 0; i < 64; ++i) {
            const uint8_t value = ctx.mmu.read8(fs_virtual(address) + i);
            if (value == 0) {
                return !path.empty() && path[0] == '/' && path.find("..") == std::string::npos
                    && path.find("//") == std::string::npos && path.find("/dev/") != 0;
            }
            if (value < 0x20 || value > 0x7E) {
                return false;
            }
            path += char(value);
        }
        return false;
    }

    int32_t ioctl(CPUContext& ctx, const IpcRequest& req) override {
        vnand_init();
        const uint32_t out = fs_virtual(req.out_buf), in = fs_virtual(req.in_buf);
        if (req.ioctl_cmd == 11) {
            const uint32_t slot = req.fd - VNAND_FD_BASE;
            if (slot >= VNAND_FD_MAX || !g_vnand_handles[slot].open || req.out_size < 8 || !fs_span(out, 8)) {
                return IPC_EINVAL;
            }
            const auto& handle = g_vnand_handles[slot];
            ctx.mmu.write32(out, uint32_t(g_vnand_files[handle.file_idx].data.size()));
            ctx.mmu.write32(out + 4, handle.pos);
            return IPC_OK;
        }
        if (req.ioctl_cmd == 13) {
            return IPC_OK;
        }
        if (req.ioctl_cmd != 3 && req.ioctl_cmd != 6 && req.ioctl_cmd != 9) {
            return IPC_EINVAL;
        }
        const bool creating = req.ioctl_cmd != 6;
        std::string path;
        if (req.in_size < (creating ? 74u : 64u) || !fs_span(in, creating ? 74 : 64)
            || !fs_path(ctx, in + (creating ? 6 : 0), path)) {
            return IPC_EINVAL;
        }
        auto found = std::find_if(g_vnand_files.begin(), g_vnand_files.end(),
            [&](const auto& file) { return file.path == path; });
        if (creating) {
            if (path == "/" || found != g_vnand_files.end()) {
                return -105;
            }
            const auto slash = path.rfind('/');
            const std::string parent = slash == 0 ? "/" : path.substr(0, slash);
            if (parent != "/" && std::none_of(g_vnand_files.begin(), g_vnand_files.end(),
                [&](const auto& file) { return file.path == parent && file.is_directory; })) {
                std::cout << "[FS commands] missing parent " << parent << " for " << path << '\n';
                return IPC_ENOENT;
            }
            VNandFile file{path, {}};
            file.is_directory = req.ioctl_cmd == 3;
            file.uid = ctx.mmu.read32(in);
            file.gid = ctx.mmu.read16(in + 4);
            for (unsigned i = 0; i < 3; ++i) {
                file.modes[i] = ctx.mmu.read8(in + 70 + i);
                if (file.modes[i] > 3) {
                    return IPC_EINVAL;
                }
            }
            file.attribute = ctx.mmu.read8(in + 73);
            g_vnand_files.push_back(std::move(file));
            std::cout << "[FS commands] created " << path << " directory=" << (req.ioctl_cmd == 3) << '\n';
            return IPC_OK;
        }
        if (req.out_size < 74 || !fs_span(out, 74)) {
            return IPC_EINVAL;
        }
        if (found == g_vnand_files.end()) {
            return IPC_ENOENT;
        }
        for (unsigned i = 0; i < 74; ++i) {
            ctx.mmu.write8(out + i, 0);
        }
        ctx.mmu.write32(out, found->uid);
        ctx.mmu.write16(out + 4, found->gid);
        for (unsigned i = 0; i < 3; ++i) {
            ctx.mmu.write8(out + 70 + i, found->modes[i]);
        }
        ctx.mmu.write8(out + 73, found->attribute);
        return IPC_OK;
    }

    int32_t ioctlv(CPUContext& ctx, const IpcRequest& req) override {
        vnand_init();
        if (req.ioctl_cmd != 12 || req.arg_cnt_in != 1 || req.arg_cnt_out != 2 || req.ioctlv_vecs.size() != 3
            || req.ioctlv_vecs[0].len != 64 || req.ioctlv_vecs[1].len != 4 || req.ioctlv_vecs[2].len != 4
            || !fs_span(req.ioctlv_vecs[1].addr, 4) || !fs_span(req.ioctlv_vecs[2].addr, 4)) {
            return IPC_EINVAL;
        }
        std::string path;
        if (!fs_path(ctx, req.ioctlv_vecs[0].addr, path)) {
            return IPC_EINVAL;
        }
        if (path != "/" && std::none_of(g_vnand_files.begin(), g_vnand_files.end(),
            [&](const auto& file) { return file.path == path && file.is_directory; })) {
            return IPC_ENOENT;
        }
        const std::string prefix = path == "/" ? path : path + '/';
        uint32_t clusters = 0, inodes = 1;
        for (const auto& file : g_vnand_files) {
            if (file.path != path && file.path.starts_with(prefix)) {
                clusters += uint32_t((file.data.size() + 16383) / 16384);
                ++inodes;
            }
        }
        ctx.mmu.write32(fs_virtual(req.ioctlv_vecs[1].addr), clusters);
        ctx.mmu.write32(fs_virtual(req.ioctlv_vecs[2].addr), inodes);
        return IPC_OK;
    }
