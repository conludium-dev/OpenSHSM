#define main openShsmProductionMain
#include "../../outputs/shsm-research/native/sandbox.cpp"
#undef main

extern "C" void* shsm_probe_create();
extern "C" void shsm_probe_destroy(void*);
extern "C" int shsm_probe_step(void*, uint32_t, uint32_t, uint32_t*, uint32_t*, uint32_t*);

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "--experimental-recomp-smoke") {
        void* context = shsm_probe_create();
        for (uint32_t value : {0u, 1u}) {
            for (uint32_t direction : {0u, 1u}) {
                uint32_t result = 0, abi = 0, callbacks = 0;
                PhoneSettings settings;
                settings.vibrate = value;
                settings.action(direction ? "MobileSettingsVibrateRight" : "MobileSettingsVibrateLeft");
                int status = shsm_probe_step(context, value, direction, &result, &abi, &callbacks);
                if (status || !abi || callbacks != 3 || result != static_cast<uint32_t>(settings.vibrate)) {
                    shsm_probe_destroy(context);
                    return 1;
                }
            }
        }
        shsm_probe_destroy(context);
        std::cout << "OpenSHSM runtime -> original PPC static function -> native return:4cases PASS\n";
        return 0;
    }
    return openShsmProductionMain(argc, argv);
}
