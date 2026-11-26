"""Extend only the private copy of the existing virtual NAND file registry."""


def adapt(text):
    marker = '    std::vector<uint8_t> data;\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '''    bool is_directory = false;
    uint32_t uid = 0;
    uint16_t gid = 0;
    uint8_t modes[3] = {3, 3, 3};
    uint8_t attribute = 0;
''')
    marker = '    int32_t open(CPUContext& ctx, const std::string& path, uint32_t mode) override {'
    assert text.count(marker) == 1
    text = text.replace(marker, '    #include "stock_fs_commands.inc"\n\n' + marker)
    text = text.replace('if (g_vnand_files[i].path == path) {',
        'if (g_vnand_files[i].path == path && !g_vnand_files[i].is_directory) {')
    marker = '    g_vnand_init = true;\n'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '    g_vnand_files.push_back({"/", {}, true});\n')
    return text


def adapt_kernel(text):
    marker = '    return e->device->ioctl(ctx, req);'
    assert text.count(marker) == 1
    text = text.replace(marker, '''    if (std::string(e->device->get_name()) == "/dev/fs") {
        IpcRequest translated = req;
        translated.fd = e->internal_fd;
        return e->device->ioctl(ctx, translated);
    }
''' + marker)
    return text
