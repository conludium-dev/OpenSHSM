#pragma once
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>

namespace openshsm::experiment {

struct DspJobReport {
    uint64_t count = 0, started = 0, failures = 0, total_us = 0, max_us = 0;
    uint64_t max_start_gap_us = 0, max_idle_us = 0, clock_errors = 0;
    uint64_t period_max_us = 0, period_max_start_gap_us = 0, period_max_idle_us = 0;
    int64_t last_start_us = 0, last_end_us = 0, idle_us = -1;
    uint32_t last_list = 0;
    bool in_flight = false;
    int64_t in_flight_start_us = 0, busy_us = 0;
};

struct FmodEventReport {
    uint64_t returns = 0, failures = 0;
    uint32_t last_status = 0, last_error = 0;
};

struct DspSupplyReport {
    int64_t elapsed, tb_wall;
    uint64_t input32, input48, accepted, dropped, flush_accepted, flush_dropped;
    uint64_t supplied, requested, short_pulls, ring, first_tb, last_tb, frequency;
    DspJobReport jobs;
    FmodEventReport events;
};

// Counter updates and take_report() require the existing adma_mutex.
class DspSupplyObserver {
public:
    void generated(uint64_t accepted, uint64_t dropped, uint64_t ring, uint32_t rate,
        uint64_t tb, uint64_t frequency, uint64_t flush_accepted, uint64_t flush_dropped) {
        if (!enabled) {
            return;
        }
        if (rate == 32000) {
            input32 += 8;
        } else if (rate == 48000) {
            input48 += 8;
        } else {
            throw std::runtime_error("Invalid observed ADMA rate");
        }
        const auto now = std::chrono::steady_clock::now();
        if (!has_tb) {
            first_tb = tb;
            first_tb_wall = now;
            has_tb = true;
        }
        last_tb = tb;
        last_tb_wall = now;
        tb_frequency = frequency;
        synchronize(accepted, dropped, ring, flush_accepted, flush_dropped);
    }

    void synchronize(uint64_t accepted, uint64_t dropped, uint64_t ring,
        uint64_t flush_accepted, uint64_t flush_dropped) {
        if (!enabled) {
            return;
        }
        if (accepted < accepted_frames || dropped < dropped_frames ||
            flush_accepted < flushed_accepted || flush_dropped < flushed_dropped) {
            throw std::runtime_error("ADMA accounting counters regressed");
        }
        flushed_accepted = flush_accepted;
        flushed_dropped = flush_dropped;
        accepted_frames = accepted;
        dropped_frames = dropped;
        ring_frames = ring;
        check_balance();
    }

    void pulled(uint64_t requested, uint64_t supplied, uint64_t before) {
        if (!enabled) {
            return;
        }
        requested_frames += requested;
        supplied_frames += supplied;
        short_pulls += supplied < requested;
        if (supplied > before) {
            throw std::runtime_error("ADMA pull exceeds its ring");
        }
        ring_frames = before - supplied;
        check_balance();
    }

    bool is_enabled() const {
        return enabled;
    }

    void fmod_event_result(uint32_t status) {
        if (!enabled) {
            return;
        }
        ++event_stats.returns;
        event_stats.failures += status != 0;
        event_stats.last_status = status;
        if (status != 0) {
            event_stats.last_error = status;
        }
    }

    int64_t job_clock_us() const {
        if (!enabled) {
            return 0;
        }
        return std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now() - origin).count();
    }

    void job_started(int64_t start, uint32_t list) {
        if (!enabled) {
            return;
        }
        ++job_stats.started;
        job_stats.clock_errors += job_stats.in_flight;
        job_stats.in_flight = true;
        job_stats.in_flight_start_us = start;
        job_stats.last_list = list;
    }

    void job_finished(int64_t start, int64_t end, bool success, uint32_t list) {
        if (!enabled) {
            return;
        }
        ++job_stats.count;
        job_stats.failures += !success;
        job_stats.last_list = list;
        const bool matched = job_stats.in_flight && job_stats.in_flight_start_us == start;
        job_stats.in_flight = false;
        if (!matched || start < 0 || end < start || (has_job && start < job_stats.last_end_us)) {
            ++job_stats.clock_errors;
            return;
        }
        const uint64_t duration = uint64_t(end - start);
        job_stats.total_us += duration;
        job_stats.max_us = std::max(job_stats.max_us, duration);
        job_stats.period_max_us = std::max(job_stats.period_max_us, duration);
        if (has_job) {
            const uint64_t gap = uint64_t(start - job_stats.last_start_us);
            const uint64_t idle = uint64_t(start - job_stats.last_end_us);
            job_stats.max_start_gap_us = std::max(job_stats.max_start_gap_us, gap);
            job_stats.max_idle_us = std::max(job_stats.max_idle_us, idle);
            job_stats.period_max_start_gap_us = std::max(job_stats.period_max_start_gap_us, gap);
            job_stats.period_max_idle_us = std::max(job_stats.period_max_idle_us, idle);
        }
        has_job = true;
        job_stats.last_start_us = start;
        job_stats.last_end_us = end;
    }

    std::optional<DspSupplyReport> take_report(
        std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now()) {
        if (!enabled) {
            return std::nullopt;
        }
        const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
            now - origin).count();
        if (elapsed < next_report_us) {
            return std::nullopt;
        }
        next_report_us = elapsed + 1000000;
        const auto tb_wall = has_tb ? std::chrono::duration_cast<std::chrono::microseconds>(
            last_tb_wall - first_tb_wall).count() : 0;
        auto jobs = job_stats;
        jobs.idle_us = has_job && !jobs.in_flight ? std::max<int64_t>(0, elapsed - jobs.last_end_us) : -1;
        jobs.busy_us = jobs.in_flight ? jobs.in_flight_start_us < 0 ? -1
            : std::max<int64_t>(0, elapsed - jobs.in_flight_start_us) : 0;
        job_stats.period_max_us = job_stats.period_max_start_gap_us = job_stats.period_max_idle_us = 0;
        return DspSupplyReport{elapsed, tb_wall, input32, input48, accepted_frames, dropped_frames,
            flushed_accepted, flushed_dropped, supplied_frames, requested_frames, short_pulls,
            ring_frames, first_tb, last_tb, tb_frequency, jobs, event_stats};
    }

    static void write_report(std::ostream& output, const DspSupplyReport& report) {
        std::ostringstream rendered;
        rendered << "[ADMAAccounting] wallUs=" << report.elapsed << " input32=" << report.input32
               << " input48=" << report.input48 << " accepted=" << report.accepted
               << " dropped=" << report.dropped << " flushAccepted=" << report.flush_accepted
               << " flushDropped=" << report.flush_dropped << " supplied=" << report.supplied
               << " requested=" << report.requested << " short=" << report.short_pulls
               << " ring=" << report.ring << " tbFirst=" << report.first_tb << " tbLast=" << report.last_tb
               << " tbFrequency=" << report.frequency << " tbWallUs=" << report.tb_wall << '\n';
        const auto& jobs = report.jobs;
        rendered << "[AXJobAccounting] wallUs=" << report.elapsed << " jobs=" << jobs.count
               << " started=" << jobs.started << " failures=" << jobs.failures << " executeUs=" << jobs.total_us
               << " maxExecuteUs=" << jobs.max_us << " maxStartGapUs=" << jobs.max_start_gap_us
               << " maxIdleUs=" << jobs.max_idle_us << " intervalMaxExecuteUs=" << jobs.period_max_us
               << " intervalMaxStartGapUs=" << jobs.period_max_start_gap_us
               << " intervalMaxIdleUs=" << jobs.period_max_idle_us << " idleUs=" << jobs.idle_us
               << " lastStartUs=" << jobs.last_start_us << " lastEndUs=" << jobs.last_end_us
               << " lastList=" << jobs.last_list << " clockErrors=" << jobs.clock_errors
               << " inFlight=" << jobs.in_flight << " inFlightStartUs=" << jobs.in_flight_start_us
               << " busyUs=" << jobs.busy_us << '\n';
        rendered << "[FMODEventAccounting] wallUs=" << report.elapsed
                 << " returns=" << report.events.returns << " failures=" << report.events.failures
                 << " lastStatus=" << report.events.last_status << " lastError=" << report.events.last_error << '\n';
        output << rendered.str();
    }

private:
    void check_balance() const {
        if (supplied_frames > accepted_frames || accepted_frames - supplied_frames != ring_frames) {
            throw std::runtime_error("ADMA accepted/supplied/ring balance failed");
        }
    }

    bool enabled = std::getenv("NWII_DSP_SUPPLY") != nullptr;
    bool has_tb = false;
    bool has_job = false;
    DspJobReport job_stats;
    FmodEventReport event_stats;
    std::chrono::steady_clock::time_point origin = std::chrono::steady_clock::now();
    std::chrono::steady_clock::time_point first_tb_wall, last_tb_wall;
    int64_t next_report_us = 1000000;
    uint64_t input32 = 0, input48 = 0, accepted_frames = 0, dropped_frames = 0;
    uint64_t flushed_accepted = 0, flushed_dropped = 0, supplied_frames = 0, requested_frames = 0;
    uint64_t short_pulls = 0, ring_frames = 0, first_tb = 0, last_tb = 0, tb_frequency = 0;
};

inline DspSupplyObserver dsp_supply_observer;

}
