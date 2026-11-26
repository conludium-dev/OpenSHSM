void experiment_di_burst_es_reply(CPUContext& context, uint64_t) {
    if (!experimentDiBurstFirstRetired) {
        EventScheduler::get().schedule_after(1, experiment_di_burst_es_reply);
        return;
    }
    hw::experiment_fixture_reply_after(0x135e0140, 1, [](CPUContext& active, uint64_t) {
        const auto result = experiment_ipc_open_packet(active, 0x135e0140);
        if (result != 4) {
            throw std::runtime_error("Concurrent ES shared-kernel FD outside measured profile");
        }
        experimentDiBurstReplyOwner = 0x135e0140;
        ++stmProduced;
        std::cout << "DI_BURST_ES_REPLY " << result << std::endl;
    });
}

void experiment_di_burst_reply_begin() {
    hw::experiment_fixture_reply_after(0x135e0080, 65, [](CPUContext& active, uint64_t) {
        experiment_di86_dispatch(active, 0x135e0080);
        ++stmProduced;
        std::cout << "DI_BURST_86_REPLY" << std::endl;
        EventScheduler::get().schedule_after(1, experiment_di_burst_es_reply);
    });
}
