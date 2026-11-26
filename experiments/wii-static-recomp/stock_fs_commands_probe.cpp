#include <processor_adapter.h>
#include "runtime/devices.h"
#include "runtime/ios_kernel.h"
#include <iostream>
#include <memory>

int main(int argc, char**) {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    auto fs = nwii::runtime::devices::create_fs_device();
    using nwii::runtime::IpcRequest;
    constexpr uint32_t input = 0x80550000, output = 0x80550100;
    const auto path = [&](uint32_t address, const std::string& value) {
        for (unsigned i = 0; i < 64; ++i) {
            ctx.mmu.write8(address + i, i < value.size() ? value[i] : 0);
        }
    };
    path(input + 6, "/Store.000");
    ctx.mmu.write32(input, 0x1001);
    ctx.mmu.write16(input + 4, 0x1234);
    for (unsigned i = 0; i < 3; ++i) {
        ctx.mmu.write8(input + 70 + i, i + 1);
    }
    ctx.mmu.write8(input + 73, 7);
    IpcRequest request{};
    request.ioctl_cmd = 9;
    request.in_buf = input;
    request.in_size = 74;
    const auto created = fs->ioctl(ctx, request);
    const auto fd = fs->open(ctx, "/Store.000", 3);
    if (argc > 1) {
        if (created != 0 || fd != -106) {
            return 1;
        }
        std::cout << "BASELINE_FS_FALSE_CREATE_SUCCESS_REPRODUCED\n";
        return 0;
    }
    if (created != 0 || fd < 20 || fs->ioctl(ctx, request) != -105) {
        return 2;
    }
    path(input, "/Store.000");
    request.ioctl_cmd = 6;
    request.in_size = 64;
    request.out_buf = output;
    request.out_size = 74;
    ctx.mmu.write8(output - 1, 0xCD);
    ctx.mmu.write8(output + 74, 0xCD);
    if (fs->ioctl(ctx, request) != 0 || ctx.mmu.read32(output) != 0x1001
        || ctx.mmu.read16(output + 4) != 0x1234 || ctx.mmu.read8(output + 73) != 7
        || ctx.mmu.read8(output - 1) != 0xCD || ctx.mmu.read8(output + 74) != 0xCD) {
        return 3;
    }
    for (unsigned i = 0; i < 257; ++i) {
        ctx.mmu.write8(input + i, uint8_t(i));
    }
    if (fs->write(ctx, fd, input, 257) != 257 || fs->seek(ctx, fd, 0, 0) != 0
        || fs->read(ctx, fd, output, 257) != 257 || fs->read(ctx, fd, output, 1) != 0) {
        return 4;
    }
    for (unsigned i = 0; i < 257; ++i) {
        if (ctx.mmu.read8(output + i) != uint8_t(i)) {
            return 5;
        }
    }
    request.ioctl_cmd = 11;
    request.fd = fd;
    request.out_size = 8;
    if (fs->ioctl(ctx, request) != 0 || ctx.mmu.read32(output) != 257 || ctx.mmu.read32(output + 4) != 257) {
        return 6;
    }
    fs->close(ctx, fd);
    const auto reopened = fs->open(ctx, "/Store.000", 1);
    if (reopened < 20 || fs->read(ctx, reopened, output, 257) != 257) {
        return 7;
    }
    path(input, "/");
    request.ioctl_cmd = 12;
    request.arg_cnt_in = 1;
    request.arg_cnt_out = 2;
    request.ioctlv_vecs = {{input, 64}, {output, 4}, {output + 4, 4}};
    if (fs->ioctlv(ctx, request) != 0 || ctx.mmu.read32(output) != 5 || ctx.mmu.read32(output + 4) != 6) {
        return 8;
    }
    path(input, "/missing");
    if (fs->ioctlv(ctx, request) != -106) {
        return 9;
    }
    request.ioctl_cmd = 9;
    request.in_size = 74;
    request.in_buf = input;
    path(input + 6, "/../Store.001");
    if (fs->ioctl(ctx, request) != -4) {
        return 10;
    }
    path(input + 6, "/Store.001");
    request.in_size = 73;
    if (fs->ioctl(ctx, request) != -4 || fs->open(ctx, "/Store.001", 1) != -106) {
        return 11;
    }
    request.in_size = 74;
    request.in_buf = 0xFFFFFFF0;
    if (fs->ioctl(ctx, request) != -4) {
        return 12;
    }
    auto& kernel = nwii::runtime::IOSKernel::get();
    kernel.init();
    kernel.register_device(std::move(fs));
    const auto guest_fd = kernel.open(ctx, "/Store.000", 1);
    request.ioctl_cmd = 11;
    request.fd = guest_fd;
    const auto stats = kernel.ioctl(ctx, request);
    if (guest_fd < 0 || guest_fd >= 20 || stats != 0
        || ctx.mmu.read32(output) != 257 || ctx.mmu.read32(output + 4) != 0) {
        std::cerr << "Kernel stats fd=" << guest_fd << " result=" << stats
            << " size=" << ctx.mmu.read32(output) << " position=" << ctx.mmu.read32(output + 4) << '\n';
        return 13;
    }
    for (unsigned i = 0; i < 74; ++i) {
        ctx.mmu.write8(input + i, 0);
    }
    for (unsigned i = 0; i < 3; ++i) {
        ctx.mmu.write8(input + 70 + i, 3);
    }
    request.ioctl_cmd = 3;
    request.in_buf = input;
    request.in_size = 74;
    path(input + 6, "/tmp");
    if (kernel.ioctl(ctx, request) != 0 || kernel.ioctl(ctx, request) != -105) {
        return 14;
    }
    request.ioctl_cmd = 9;
    path(input + 6, "/tmp/Profile");
    if (kernel.ioctl(ctx, request) != 0 || kernel.open(ctx, "/tmp/Profile", 3) < 1) {
        return 15;
    }
    path(input + 6, "/bad/Profile");
    if (kernel.ioctl(ctx, request) != -106) {
        return 16;
    }
    path(input + 6, "/Invalid");
    ctx.mmu.write8(input + 70, 4);
    if (kernel.ioctl(ctx, request) != -4 || kernel.open(ctx, "/Invalid", 3) != -106) {
        return 17;
    }
    std::cout << "FS_CREATE_METADATA_USAGE_COMPONENT_PASS create/open/write/read/reopen/duplicates/bounds/kernel-handles/directories\n";
}
