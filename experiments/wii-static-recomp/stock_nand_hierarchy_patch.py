"""Add title-directory protocol and consistent parents to existing private ES/FS copies."""


def adapt_es(text):
    marker = '    int32_t ioctlv(CPUContext& ctx, const IpcRequest& req) override {\n'
    assert text.count(marker) == 1
    return '#include "stock_nand_paths.h"\n' + text.replace(marker,
        marker + '        #include "stock_es_title_directory.inc"\n')


def adapt_fs(text):
    marker = 'static constexpr int VNAND_FD_BASE = 20;'
    at = text.index(marker)
    before = text[:at]
    end = before.rindex('\n}')
    text = before[:end] + '\n    #include "stock_nand_hierarchy.inc"' + before[end:] + text[at:]
    return '#include "runtime/config.h"\n#include "stock_nand_paths.h"\n' + text
