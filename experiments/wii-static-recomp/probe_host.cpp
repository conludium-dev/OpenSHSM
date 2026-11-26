#include "../../outputs/shsm-research/native/PhoneSettings.h"
#include <cstdint>
#include <iostream>

extern "C" void* shsm_probe_create();
extern "C" void shsm_probe_destroy(void*);
extern "C" int shsm_probe_step(void*, uint32_t, uint32_t, uint32_t*, uint32_t*, uint32_t*);

int main() {
    void* context = shsm_probe_create();
    uint32_t value, direction;
    while (std::cin >> value >> direction) {
        uint32_t result = 0, abi = 0, callbacks = 0;
        int status = shsm_probe_step(context, value, direction, &result, &abi, &callbacks);
        PhoneSettings native;
        native.vibrate = value <= 1 ? value : 0;
        native.action(direction ? "MobileSettingsVibrateRight" : "MobileSettingsVibrateLeft");
        bool nativeEquivalent = value > 1 || result == static_cast<uint32_t>(native.vibrate);
        std::cout << value << ' ' << direction << ' ' << result << ' ' << abi << ' ' << callbacks << ' '
                  << status << ' ' << nativeEquivalent << '\n';
        if (status || !abi || callbacks != 3 || !nativeEquivalent) {
            shsm_probe_destroy(context);
            return 1;
        }
    }
    shsm_probe_destroy(context);
}
