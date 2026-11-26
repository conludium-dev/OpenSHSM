"""Back the existing Wii title-data VNandFile registry with a host snapshot."""


def adapt_source(source):
    before = 'namespace nwii::runtime::devices {\n'
    assert source.count(before) == 1
    source = source.replace(before,
        '#include <filesystem>\n#include <fstream>\n#include <iterator>\n#include <cstdint>\n#include <cstdlib>\n'
        + before, 1)
    before = 'static bool g_vnand_init = false;\n'
    assert source.count(before) == 1
    source = source.replace(before, before + '#include "stock_vnand_persistence.h"\n', 1)

    before = '    #include "stock_nand_hierarchy.inc"\n'
    assert source.count(before) == 1
    source = source.replace(before, before +
        '    if (!vnand_restore()) {\n'
        '        std::cout << "[FS persist] save snapshot is invalid; preserving it read-only\\n";\n'
        '    }\n', 1)

    before = '            g_vnand_handles[slot].open = false;\n            return IPC_OK;\n'
    assert source.count(before) == 1
    source = source.replace(before,
        '            const auto& path = g_vnand_files[g_vnand_handles[slot].file_idx].path;\n'
        '            const bool game_data = path.starts_with(k_vnand_title_data);\n'
        '            g_vnand_handles[slot].open = false;\n'
        '            if (game_data && !vnand_persist()) {\n'
        '                std::cout << "[FS persist] failed after close: " << path << \'\\n\';\n'
        '                return IPC_EINVAL;\n'
        '            }\n'
        '            return IPC_OK;\n', 1)
    return source


def adapt_rename(source):
    before = '        std::cout << "[FS rename] " << source << " -> " << destination << " nodes=" << planned.size() << \'\\n\';\n        return IPC_OK;\n'
    assert source.count(before) == 1
    return source.replace(before,
        '        std::cout << "[FS rename] " << source << " -> " << destination << " nodes=" << planned.size() << \'\\n\';\n'
        '        if ((source.starts_with(k_vnand_title_data) || destination.starts_with(k_vnand_title_data))\n'
        '            && !vnand_persist()) {\n'
        '            std::cout << "[FS persist] failed after rename\\n";\n'
        '            return IPC_EINVAL;\n'
        '        }\n'
        '        return IPC_OK;\n', 1)
