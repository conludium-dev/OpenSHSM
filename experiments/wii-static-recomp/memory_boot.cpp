#include "memory_frontend.h"
#define ProcessorContext MemoryContext
#define SHSM_FPSCR_MAIN_NAME memory_boot_main
#include "fpscr_boot.cpp"
#undef SHSM_FPSCR_MAIN_NAME
#undef ProcessorContext

int main(int argc, char** argv) {
    return memory_boot_main(argc, argv);
}
