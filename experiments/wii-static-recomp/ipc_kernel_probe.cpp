#include "runtime/ios_kernel.h"
#include <iostream>

int main() {
    nwii::runtime::CPUContext context;
    auto& kernel = nwii::runtime::IOSKernel::get();
    kernel.init();
    for (unsigned index = 0; index < 8; ++index) {
        const auto result = kernel.open(context, "/dev/openshsm_missing", 1);
        std::cout << "IPC_KERNEL_CASE " << index << ' ' << result << '\n';
    }
    return 0;
}
