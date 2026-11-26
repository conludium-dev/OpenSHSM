#include <processor_adapter.h>
#include "runtime/devices.h"
#include "runtime/ios_kernel.h"
#include "runtime/config.h"
#include <cassert>
#include <iostream>
#include <memory>

int main(int argc, char**) {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    nwii::runtime::Config::get().game_id = "R5WEA4";
    auto& kernel = nwii::runtime::IOSKernel::get();
    kernel.init();
    kernel.register_device(nwii::runtime::devices::create_fs_device());
    const auto fs = kernel.open(ctx, "/dev/fs", 0);
    constexpr uint32_t params = 0x80560000, bytes = 0x80561000;
    nwii::runtime::IpcRequest request{};
    request.fd = fs;
    request.in_buf = params;
    const auto text = [&](uint32_t address, const std::string& value) {
        assert(value.size() < 64);
        for (unsigned i = 0; i < 64; ++i) {
            ctx.mmu.write8(address + i, i < value.size() ? value[i] : 0);
        }
    };
    const auto create = [&](const std::string& path, bool directory = false) {
        for (unsigned i = 0; i < 128; ++i) {
            ctx.mmu.write8(params + i, 0);
        }
        ctx.mmu.write32(params, 7);
        ctx.mmu.write16(params + 4, 9);
        text(params + 6, path);
        for (unsigned i = 70; i < 73; ++i) {
            ctx.mmu.write8(params + i, 3);
        }
        ctx.mmu.write8(params + 73, 2);
        request.ioctl_cmd = directory ? 3 : 9;
        request.in_size = 74;
        assert(kernel.ioctl(ctx, request) == 0);
    };
    const auto rename = [&](const std::string& from, const std::string& to) {
        text(params, from);
        text(params + 64, to);
        request.ioctl_cmd = 8;
        request.in_size = 128;
        return kernel.ioctl(ctx, request);
    };
    const auto check = [&](const std::string& path, uint32_t expected) {
        const auto fd = kernel.open(ctx, path, 3);
        assert(fd >= 0 && kernel.read(ctx, fd, bytes, 4) == 4 && ctx.mmu.read32(bytes) == expected);
        assert(kernel.close(ctx, fd) == 0);
    };
    create("/tmp/sys", true);
    create("/tmp/sys/Store.000");
    create("/title/00010000/52355745/data/Store.000");
    auto fd = kernel.open(ctx, "/tmp/sys/Store.000", 3);
    ctx.mmu.write32(bytes, 0x12345678);
    assert(fd >= 0 && kernel.write(ctx, fd, bytes, 4) == 4 && kernel.close(ctx, fd) == 0);
    const std::string target = "/title/00010000/52355745/data/Store.000";
    if (argc > 1) {
        assert(rename("/tmp/sys/Store.000", target) == -4);
        check("/tmp/sys/Store.000", 0x12345678);
        std::cout << "BASELINE_RENAME_UNSUPPORTED_REPRODUCED\n";
        return 0;
    }
    assert(rename("/tmp/sys/Store.000", target) == 0);
    assert(kernel.open(ctx, "/tmp/sys/Store.000", 3) == -106);
    check(target, 0x12345678);
    assert(rename(target, target) == 0);
    fd = kernel.open(ctx, target, 3);
    assert(rename(target, "/tmp/sys/Blocked") == -101);
    assert(kernel.close(ctx, fd) == 0);
    assert(rename(target, "/missing-parent/Store") == -106);
    assert(rename("/missing-source", "/tmp/sys/Other") == -106);
    assert(rename(target, "/") == -4);
    assert(rename(target, "/tmp/../Other") == -4);
    request.in_size = 127;
    assert(kernel.ioctl(ctx, request) == -4);
    request.in_size = 128;
    request.in_buf = 0xFFFFFFF0;
    assert(kernel.ioctl(ctx, request) == -4);
    request.in_buf = params;
    create("/tmp/tree", true);
    create("/tmp/tree/sub", true);
    create("/tmp/tree/sub/file");
    fd = kernel.open(ctx, "/tmp/tree/sub/file", 3);
    ctx.mmu.write32(bytes, 0x87654321);
    assert(kernel.write(ctx, fd, bytes, 4) == 4 && kernel.close(ctx, fd) == 0);
    assert(rename("/tmp/tree", "/tmp/tree/sub/new") == -4);
    assert(rename("/tmp/tree", "/tmp/moved") == 0);
    check("/tmp/moved/sub/file", 0x87654321);
    check(target, 0x12345678);
    create("/tmp/other", true);
    create("/tmp/other/file");
    assert(rename("/tmp/moved", "/tmp/other") == -105);
    check("/tmp/moved/sub/file", 0x87654321);
    std::cout << "FS_RENAME_COMPONENT_PASS replace/reopen/subtree/guards/rollback/handle-policy\n";
}
