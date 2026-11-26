#include "stock_adma_accounting.h"
#include <cassert>
#include <sstream>

int main() {
    using namespace openshsm::experiment;
    using namespace std::chrono_literals;
    DspSupplyObserver observer;
    const auto now = std::chrono::steady_clock::now();
    if (!observer.is_enabled()) {
        observer.job_finished(1, 2, false, 123);
        observer.fmod_event_result(86);
        assert(observer.job_clock_us() == 0);
        assert(!observer.take_report(now + 2s));
        std::cout << "DSP_JOB_ACCOUNTING_DISABLED_PASS\n";
        return 0;
    }
    assert(observer.job_clock_us() >= 0);
    const auto finish = [&](int64_t start, int64_t end, bool success, uint32_t list) {
        observer.job_started(start, list);
        observer.job_finished(start, end, success, list);
    };
    finish(1000, 1125, true, 1);
    finish(4000, 4200, false, 2);
    finish(54000, 54010, true, 3);
    finish(50000, 50010, true, 4);
    finish(-1, 0, false, 5);
    for (uint32_t status : {0u, 86u, 0u, 36u, UINT32_MAX}) {
        observer.fmod_event_result(status);
    }
    const auto first = observer.take_report(now + 2s);
    assert(first);
    const auto& a = first->jobs;
    assert(a.count == 5 && a.started == 5 && a.failures == 2 && a.clock_errors == 2);
    assert(!a.in_flight && a.busy_us == 0);
    assert(a.total_us == 335 && a.max_us == 200 && a.period_max_us == 200);
    assert(a.max_start_gap_us == 50000 && a.period_max_start_gap_us == 50000);
    assert(a.max_idle_us == 49800 && a.period_max_idle_us == 49800);
    assert(a.last_start_us == 54000 && a.last_end_us == 54010 && a.last_list == 5);
    assert(a.idle_us >= 1900000);
    assert(first->events.returns == 5 && first->events.failures == 3);
    assert(first->events.last_status == UINT32_MAX && first->events.last_error == UINT32_MAX);
    finish(100000, 100050, true, 6);
    observer.fmod_event_result(0);
    assert(!observer.take_report(now + 2500ms));
    const auto second = observer.take_report(now + 4s);
    assert(second);
    const auto& b = second->jobs;
    assert(b.count == 6 && b.failures == 2 && b.clock_errors == 2);
    assert(b.total_us == 385 && b.max_us == 200 && b.period_max_us == 50);
    assert(b.max_start_gap_us == 50000 && b.period_max_start_gap_us == 46000);
    assert(b.max_idle_us == 49800 && b.period_max_idle_us == 45990);
    assert(second->events.returns == 6 && second->events.failures == 3);
    assert(second->events.last_status == 0 && second->events.last_error == UINT32_MAX);
    observer.job_started(200000, 7);
    const auto third = observer.take_report(now + 6s);
    assert(third && third->jobs.count == 6);
    assert(third->jobs.period_max_us == 0 && third->jobs.period_max_start_gap_us == 0);
    assert(third->jobs.period_max_idle_us == 0 && third->jobs.idle_us == -1);
    assert(third->jobs.started == 7 && third->jobs.in_flight && third->jobs.busy_us >= 5700000);
    observer.job_finished(200000, 200010, true, 7);
    const auto fourth = observer.take_report(now + 8s);
    assert(fourth && fourth->jobs.count == 7 && !fourth->jobs.in_flight && fourth->jobs.busy_us == 0);
    std::ostringstream output;
    DspSupplyObserver::write_report(output, *first);
    assert(output.str().find("[ADMAAccounting] ") == 0);
    assert(output.str().find("[AXJobAccounting] ") != std::string::npos);
    assert(output.str().find(" jobs=5 started=5 failures=2 executeUs=335 ") != std::string::npos);
    assert(output.str().find(" lastList=5 clockErrors=2 inFlight=0 ") != std::string::npos);
    assert(output.str().find("[FMODEventAccounting] ") != std::string::npos);
    assert(output.str().find(" returns=5 failures=3 lastStatus=4294967295 lastError=4294967295\n") != std::string::npos);
    std::ostringstream formatted;
    formatted << std::hex << std::boolalpha;
    const auto flags = formatted.flags();
    DspSupplyObserver::write_report(formatted, *first);
    assert(formatted.str() == output.str());
    assert(formatted.flags() == flags);
    std::cout << "DSP_JOB_ACCOUNTING_INTERVALS_ERRORS_SNAPSHOT_PASS\n";
}
