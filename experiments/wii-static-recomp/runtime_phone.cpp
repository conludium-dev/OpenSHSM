#include "../../outputs/shsm-research/native/PhoneSettings.h"
#include <cstdint>
#include <iostream>
#include <memory>
#include <stdexcept>

extern "C" void* shsm_probe_create();
extern "C" void shsm_probe_destroy(void*);
extern "C" int shsm_probe_step(void*, uint32_t, uint32_t, uint32_t*, uint32_t*, uint32_t*);

namespace {
bool experimentalPhoneEnabled = false;
unsigned experimentalPhoneCalls = 0;

struct GuestDeleter {
    void operator()(void* context) const {
        shsm_probe_destroy(context);
    }
};

std::unique_ptr<void, GuestDeleter> experimentalGuest;
}

struct ExperimentalPhoneSettings : PhoneSettings {
    bool action(const std::string& name) {
        if (!experimentalPhoneEnabled || (name != "MobileSettingsVibrateLeft" && name != "MobileSettingsVibrateRight")) {
            return PhoneSettings::action(name);
        }
        if (!experimentalGuest) {
            experimentalGuest.reset(shsm_probe_create());
        }
        uint32_t result = 0, abi = 0, callbacks = 0;
        const uint32_t prior = static_cast<uint32_t>(vibrate);
        const uint32_t direction = name == "MobileSettingsVibrateRight";
        const int status = shsm_probe_step(experimentalGuest.get(), prior, direction, &result, &abi, &callbacks);
        if (status || !abi || callbacks != 3 || result > 1) {
            throw std::runtime_error("Original PPC phone callback failed; native fallback is forbidden");
        }
        vibrate = static_cast<int>(result);
        ++experimentalPhoneCalls;
        std::cout << "SHSM_RECOMP_UI action=" << name << " prior=" << prior << " result=" << result
                  << " abi=" << abi << " callbacks=" << callbacks << '\n';
        return true;
    }
};

// PC adaptation: opt-in type injection applies only to this private translation unit.
#define PhoneSettings ExperimentalPhoneSettings
#define main openShsmProductionMain
#include "../../outputs/shsm-research/native/sandbox.cpp"
#undef main
#undef PhoneSettings

int main(int argc, char** argv) {
    std::vector<char*> forwarded;
    for (int index = 0; index < argc; ++index) {
        if (index > 0 && std::string(argv[index]) == "--experimental-recomp-phone") {
            if (experimentalPhoneEnabled) {
                std::cerr << "Duplicate experimental phone option\n";
                return 2;
            }
            experimentalPhoneEnabled = true;
        } else {
            forwarded.push_back(argv[index]);
        }
    }
    if (forwarded.size() < 2) {
        std::cerr << "An existing OpenSHSM command or scene path is required\n";
        return 2;
    }
    const int forwardedCount = static_cast<int>(forwarded.size());
    forwarded.push_back(nullptr);
    const int result = openShsmProductionMain(forwardedCount, forwarded.data());
    if (experimentalPhoneEnabled) {
        std::cout << "SHSM_RECOMP_SUMMARY calls=" << experimentalPhoneCalls << " exit=" << result << '\n';
    }
    return result;
}
