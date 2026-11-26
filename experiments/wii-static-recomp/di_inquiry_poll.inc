void experiment_inquiry_poll(CPUContext&, uint64_t) {
    if (!experimentInquiryTicketReturned) {
        EventScheduler::get().schedule_after(1, experiment_inquiry_poll);
        return;
    }
    hw::experiment_fixture_reply_after(0x135e00e0, 1, [](CPUContext& active, uint64_t) {
        experiment_inquiry_dispatch(active);
        ++stmProduced;
    });
}
