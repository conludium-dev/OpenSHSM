    const auto ensure_directory = [](const std::string& path) {
        if (std::none_of(g_vnand_files.begin(), g_vnand_files.end(), [&](const auto& node) { return node.path == path; })) {
            g_vnand_files.push_back({path, {}, true});
        }
    };
    ensure_directory("/tmp");
    const size_t existing_count = g_vnand_files.size();
    for (size_t i = 0; i < existing_count; ++i) {
        const std::string path = g_vnand_files[i].path;
        for (size_t slash = path.find('/', 1); slash != std::string::npos; slash = path.find('/', slash + 1)) {
            ensure_directory(path.substr(0, slash));
        }
    }
    const auto& game_id = nwii::runtime::Config::get().game_id;
    if (game_id.size() >= 4) {
        uint32_t title_low = 0;
        for (unsigned i = 0; i < 4; ++i) {
            title_low = (title_low << 8) | uint8_t(game_id[i]);
        }
        const auto path = openshsm::experiment::title_data_path(0x00010000, title_low);
        for (size_t slash = path.find('/', 1); slash != std::string::npos; slash = path.find('/', slash + 1)) {
            ensure_directory(path.substr(0, slash));
        }
        ensure_directory(path);
    }
