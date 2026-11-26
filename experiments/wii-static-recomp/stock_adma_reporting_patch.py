"""Report existing ADMA counters on the host, outside the audio callback and ring lock."""


def dsp(source):
    marker = 'static void adma_event_cb(CPUContext& ctx, uint64_t late);'
    if source.count(marker) != 1 or 'void dsp_audio_report()' in source:
        raise ValueError('DSP report integration site differs')
    function = '''void dsp_audio_report() {
    auto& observer = openshsm::experiment::dsp_supply_observer;
    if (!observer.is_enabled()) {
        return;
    }
    std::optional<openshsm::experiment::DspSupplyReport> report;
    {
        std::lock_guard<std::mutex> lock(adma_mutex);
        report = observer.take_report();
    }
    if (report) {
        openshsm::experiment::DspSupplyObserver::write_report(std::cout, *report);
    }
}

'''
    return source.replace(marker, function + marker, 1)


def host(source):
    changes = [
        ('#include "stock_audio_callback.h"',
            '#include "stock_audio_callback.h"\nnamespace nwii::runtime::hw { void dsp_audio_report(); }'),
        ('        audio_callback.report();',
            '        nwii::runtime::hw::dsp_audio_report();\n        audio_callback.report();')]
    for before, after in changes:
        if source.count(before) != 1:
            raise ValueError('Host audio report integration site differs')
        source = source.replace(before, after, 1)
    return source


def jobs(source):
    marker = 'void dsp_audio_report() {'
    helper = '''static int64_t dsp_begin_ax_job(uint32_t list) {
    auto& observer = openshsm::experiment::dsp_supply_observer;
    if (!observer.is_enabled()) {
        return 0;
    }
    std::lock_guard<std::mutex> lock(adma_mutex);
    const auto start = observer.job_clock_us();
    observer.job_started(start, list);
    return start;
}

static void dsp_record_ax_job(int64_t start, bool success, uint32_t list) {
    auto& observer = openshsm::experiment::dsp_supply_observer;
    if (!observer.is_enabled()) {
        return;
    }
    const auto end = observer.job_clock_us();
    std::lock_guard<std::mutex> lock(adma_mutex);
    observer.job_finished(start, end, success, list);
}

'''
    changes = [
        (marker, helper + marker),
        ('                            try {\n                                dsp_ax_execution.execute(',
            '                            const auto dsp_job_start = dsp_begin_ax_job(mail);\n'
            '                            try {\n                                dsp_ax_execution.execute('),
        ('                            } catch (const std::exception& error) {\n                                std::cerr << "[AXWii] refused command list:',
            '                            } catch (const std::exception& error) {\n'
            '                                dsp_record_ax_job(dsp_job_start, false, mail);\n'
            '                                std::cerr << "[AXWii] refused command list:'),
        ('                            if (!g_ctx_ptr->is_running) { return; }',
            '                            dsp_record_ax_job(dsp_job_start, g_ctx_ptr->is_running, mail);\n'
            '                            if (!g_ctx_ptr->is_running) { return; }')]
    for before, after in changes:
        if source.count(before) != 1:
            raise ValueError('AX job accounting integration site differs')
        source = source.replace(before, after, 1)
    return source
