    int32_t rename_node(CPUContext& ctx, const IpcRequest& req) {
        const auto input = fs_virtual(req.in_buf);
        std::string source, destination;
        if (req.in_size < 128 || !fs_span(input, 128) || !fs_path(ctx, input, source)
            || !fs_path(ctx, input + 64, destination) || source == "/" || destination == "/"
            || source.back() == '/' || destination.back() == '/') {
            return IPC_EINVAL;
        }
        const auto find = [&](const std::string& path) {
            for (size_t i = 0; i < g_vnand_files.size(); ++i) {
                if (g_vnand_files[i].path == path) {
                    return i;
                }
            }
            return g_vnand_files.size();
        };
        const auto from = find(source), to = find(destination);
        if (from == g_vnand_files.size()) {
            return IPC_ENOENT;
        }
        if (source == destination) {
            return IPC_OK;
        }
        const auto prefix = source + '/';
        if (destination.starts_with(prefix)) {
            return IPC_EINVAL;
        }
        const auto slash = destination.rfind('/');
        const auto parent = find(slash == 0 ? "/" : destination.substr(0, slash));
        if (parent == g_vnand_files.size() || !g_vnand_files[parent].is_directory) {
            return IPC_ENOENT;
        }
        if (to != g_vnand_files.size()) {
            if (g_vnand_files[from].is_directory != g_vnand_files[to].is_directory) {
                return IPC_EINVAL;
            }
            for (const auto& file : g_vnand_files) {
                if (file.path.starts_with(destination + '/')) {
                    return -105;
                }
            }
        }
        std::vector<std::pair<size_t, std::string>> planned;
        for (size_t i = 0; i < g_vnand_files.size(); ++i) {
            const auto& path = g_vnand_files[i].path;
            if (i == from || (g_vnand_files[from].is_directory && path.starts_with(prefix))) {
                auto next = destination + path.substr(source.size());
                if (next.size() >= 64) {
                    return IPC_EINVAL;
                }
                const auto collision = find(next);
                if (collision != g_vnand_files.size() && collision != to) {
                    return -105;
                }
                planned.emplace_back(i, std::move(next));
            }
        }
        for (const auto& handle : g_vnand_handles) {
            if (handle.open && (size_t(handle.file_idx) == to || std::any_of(planned.begin(), planned.end(),
                [&](const auto& move) { return move.first == size_t(handle.file_idx); }))) {
                return -101;
            }
        }
        if (to != g_vnand_files.size()) {
            g_vnand_files[to] = VNandFile{};
        }
        for (auto& move : planned) {
            g_vnand_files[move.first].path.swap(move.second);
        }
        std::cout << "[FS rename] " << source << " -> " << destination << " nodes=" << planned.size() << '\n';
        return IPC_OK;
    }
