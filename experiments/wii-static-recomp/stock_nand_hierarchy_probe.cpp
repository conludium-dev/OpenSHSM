#include <processor_adapter.h>
#include "runtime/devices.h"
#include "runtime/ios_kernel.h"
#include "runtime/config.h"
#include "stock_nand_paths.h"
#include <iostream>
#include <memory>

int main(int argc, char**) {
    auto owned = std::make_unique<nwii::runtime::ProcessorContext>();
    auto& ctx = *owned;
    nwii::runtime::Config::get().game_id = "R5WEA4";
    auto& kernel = nwii::runtime::IOSKernel::get();
    kernel.init();
    kernel.register_device(nwii::runtime::devices::create_fs_device());
    kernel.register_device(nwii::runtime::devices::create_es_device());
    const auto es = kernel.open(ctx, "/dev/es", 0);
    const auto fs = kernel.open(ctx, "/dev/fs", 0);
    constexpr uint32_t input = 0x80550000, output = 0x80550100, params = 0x80550200;
    ctx.mmu.write32(input, 0x00010000);
    ctx.mmu.write32(input + 4, 0x52355745);
    for (unsigned i = 0; i < 80; ++i) {
        ctx.mmu.write8(output - 8 + i, 0xCD);
    }
    nwii::runtime::IpcRequest request{};
    request.fd = es;
    request.ioctl_cmd = 0x1D;
    request.arg_cnt_in = 1;
    request.arg_cnt_out = 1;
    request.ioctlv_vecs = {{input, 8}, {output, 64}};
    if (kernel.ioctlv(ctx, request) != 0) {
        return 1;
    }
    if (argc > 1) {
        if (ctx.mmu.read8(output) != 0) {
            return 2;
        }
        std::cout << "BASELINE_ES_EMPTY_TITLE_DIRECTORY_REPRODUCED\n";
        return 0;
    }
    const std::string expected = "/title/00010000/52355745/data";
    for (unsigned i = 0; i <= expected.size(); ++i) {
        if (ctx.mmu.read8(output + i) != (i == expected.size() ? 0 : expected[i])) {
            return 3;
        }
    }
    if (ctx.mmu.read8(output - 1) != 0xCD || ctx.mmu.read8(output + 30) != 0xCD) {
        return 4;
    }
    for (unsigned i = 0; i < 4; ++i) {
        auto invalid = request;
        if (i == 0) {
            invalid.ioctlv_vecs[0].len = 7;
        } else if (i == 1) {
            invalid.ioctlv_vecs[1].len = 29;
        } else if (i == 2) {
            invalid.ioctlv_vecs[1].addr = 0xFFFFFFF0;
        } else {
            invalid.ioctlv_vecs.pop_back();
        }
        if (kernel.ioctlv(ctx, invalid) != -4 || ctx.mmu.read8(output) != '/') {
            return 5;
        }
    }
    const auto path = [&](const std::string& value) {
        for (unsigned i = 0; i < 74; ++i) {
            ctx.mmu.write8(params + i, 0);
        }
        for (unsigned i = 0; i < value.size(); ++i) {
            ctx.mmu.write8(params + 6 + i, value[i]);
        }
        for (unsigned i = 0; i < 3; ++i) {
            ctx.mmu.write8(params + 70 + i, 3);
        }
    };
    request = {};
    request.fd = fs;
    request.ioctl_cmd = 9;
    request.in_buf = params;
    request.in_size = 74;
    const auto saved_path = expected + "/Store.000";
    path(saved_path);
    if (kernel.ioctl(ctx, request) != 0) {
        return 6;
    }
    const auto file = kernel.open(ctx, saved_path, 3);
    ctx.mmu.write32(input, 0x12345678);
    if (file < 0 || kernel.write(ctx, file, input, 4) != 4 || kernel.seek(ctx, file, 0, 0) != 0
        || kernel.read(ctx, file, output, 4) != 4 || ctx.mmu.read32(output) != 0x12345678) {
        return 7;
    }
    request.ioctl_cmd = 3;
    path("/tmp/sys");
    if (kernel.ioctl(ctx, request) != 0 || kernel.ioctl(ctx, request) != -105) {
        return 8;
    }
    path(expected + "/sandbox");
    if (kernel.ioctl(ctx, request) != 0) {
        return 9;
    }
    std::cout << "NAND_TITLE_HIERARCHY_COMPONENT_PASS ES/title-save/temporary-directories/bounds\n";
}
