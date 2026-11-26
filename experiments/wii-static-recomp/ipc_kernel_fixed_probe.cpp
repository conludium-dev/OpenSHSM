#include "runtime/ios_kernel.h"
#include <iostream>

class ForwardingErrorFixture final : public nwii::runtime::IDevice {
public:
    const char* get_name() const override { return "/dev/openshsm_fixture"; }
    int32_t open(nwii::runtime::CPUContext&, const std::string&, uint32_t) override { return -106; }
};

int main() {
    nwii::runtime::CPUContext context;
    auto& kernel = nwii::runtime::IOSKernel::get();
    kernel.init();
    kernel.register_device(std::make_unique<ForwardingErrorFixture>());
    for (unsigned index = 0; index < 8; ++index) {
        const auto result = kernel.open(context, "/dev/openshsm_missing", 1);
        std::cout << "IPC_KERNEL_FIXED " << index << ' ' << result << '\n';
    }
    const auto forwarded = kernel.open(context, "/dev/openshsm_fixture", 1);
    if (forwarded != -106) {
        return 9;
    }
    std::cout << "IPC_DEVICE_ERROR_FORWARDED " << forwarded << '\n';
    return 0;
}
