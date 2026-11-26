extern "C" void run_game(nwii::runtime::CPUContext&);
int main(int argc, char** argv) {
    using namespace nwii::runtime;
    SeededBatContext context;
    auto prepare = [&] {
        experimentFiniteMem2 = true;
        experimentFiniteMem2Owner = nullptr;
        experimentFiniteMem2Steps = 0;
        experimentFiniteMem2Returned = false;
        experimentDcZero = true;
        context.hid0 = 0xc200;
        context.pc = 0x80213084;
        context.lr = 0x80210ec8;
        context.msr = 0x2032;
        context.ctr = experimentFiniteMem2Count - 1;
        context.gpr[3] = experimentFiniteMem2Start + 32;
        context.gpr[4] = experimentFiniteMem2Count;
        context.gpr[5] = 0;
        context.is_running = true;
        context.vblank_pending = false;
        bootPollChecks = 37;
    };
    auto refuse = [&](const std::function<void()>& operation) {
        const auto count = bootPollChecks;
        const auto steps = experimentFiniteMem2Steps;
        const auto owner = experimentFiniteMem2Owner;
        const auto returned = experimentFiniteMem2Returned;
        bool rejected = false;
        try { operation(); } catch (const std::runtime_error&) { rejected = true; }
        if (!rejected || count != bootPollChecks || steps != experimentFiniteMem2Steps ||
            owner != experimentFiniteMem2Owner || returned != experimentFiniteMem2Returned) {
            throw std::runtime_error("Finite clear guard accepted or mutated accounting");
        }
    };
    for (unsigned test = 0; test < 12; ++test) {
        prepare();
        if (test == 0) { context.pc = 0x80213080; }
        if (test == 1) { context.msr = 0x2030; }
        if (test == 2) { context.gpr[3] += 32; }
        if (test == 3) { context.gpr[4] -= 1; }
        if (test == 4) { context.ctr -= 1; }
        if (test == 5) { context.gpr[5] = 7; }
        if (test == 6) { context.hid0 = 0x8200; }
        if (test == 7) { experimentDcZero = false; }
        if (test == 8) { experimentFiniteMem2Returned = true; }
        if (test == 9) { experimentFiniteMem2Owner = reinterpret_cast<CPUContext*>(1); }
        if (test == 10) { context.vblank_pending = true; }
        if (test == 11) { bootPollChecks = 1000000; }
        refuse([&] { experiment_finite_mem2_poll(context, experiment_boot_poll); });
    }
    prepare();
    if (experiment_finite_mem2_poll(context, experiment_boot_poll) || bootPollChecks != 37 || experimentFiniteMem2Steps != 1) { return 3; }
    refuse([&] { experiment_finite_mem2_poll(context, experiment_boot_poll); });
    refuse([&] { experiment_finite_mem2_return(context); });
    for (uint32_t completed = 2; completed < experimentFiniteMem2Count; ++completed) {
        context.gpr[3] = experimentFiniteMem2Start + completed * 32;
        context.ctr = experimentFiniteMem2Count - completed;
        if (experiment_finite_mem2_poll(context, experiment_boot_poll) || bootPollChecks != 37) { return 4; }
    }
    context.gpr[3] = experimentFiniteMem2End;
    context.ctr = 0;
    refuse([&] { experiment_finite_mem2_poll(context, experiment_boot_poll); });
    experiment_finite_mem2_return(context);
    if (!experimentFiniteMem2Returned || experimentFiniteMem2Steps != experimentFiniteMem2Count) { return 5; }
    refuse([&] { experiment_finite_mem2_return(context); });
    prepare();
    experimentFiniteMem2 = false;
    experiment_finite_mem2_poll(context, experiment_boot_poll);
    if (bootPollChecks != 38 || experimentFiniteMem2Steps) { return 6; }
    std::cout << "FINITE_MEM2_GUARDS 16 COUNT " << experimentFiniteMem2Count << " DISABLED_ORIGINAL_POLL\n";
    return 0;
}
