#pragma once
#include <runtime/cpu_context.h>
#include <condition_variable>
#include <stdexcept>

namespace stock_thp_snapshot {

class CpuBarrier {
public:
    enum class ClockPolicy { Freeze, Advance, Rebased };

    bool acquire(std::chrono::milliseconds timeout) {
        std::unique_lock<std::mutex> lock(mutex);
        if (state == State::Stopped) { return false; }
        if (state != State::Idle) { throw std::logic_error("CPU snapshot barrier already acquired"); }
        state = State::Requested;
        requested.store(true, std::memory_order_release);
        if (!changed.wait_for(lock, timeout, [&] { return state != State::Requested; })) {
            state = State::Idle;
            requested.store(false, std::memory_order_release);
            changed.notify_all();
            return false;
        }
        return state == State::Parked;
    }

    void release(ClockPolicy policy = ClockPolicy::Freeze) {
        std::unique_lock<std::mutex> lock(mutex);
        if (state == State::Stopped) { return; }
        if (state != State::Parked) { throw std::logic_error("CPU snapshot barrier is not parked"); }
        clock_policy = policy;
        state = State::Releasing;
        requested.store(false, std::memory_order_release);
        changed.notify_all();
        changed.wait(lock, [&] { return state == State::Idle || state == State::Stopped; });
    }

    void checkpoint(nwii::runtime::CPUContext& ctx) {
        if (!requested.load(std::memory_order_acquire)) { return; }
        std::unique_lock<std::mutex> lock(mutex);
        if (state != State::Requested) { return; }
        parked_at = std::chrono::steady_clock::now();
        state = State::Parked;
        changed.notify_all();
        while (state == State::Parked && ctx.is_running.load()) {
            changed.wait_for(lock, std::chrono::milliseconds(10));
        }
        if (!ctx.is_running.load() || state == State::Stopped) {
            state = State::Stopped;
            requested.store(false, std::memory_order_release);
        } else {
            if (clock_policy == ClockPolicy::Freeze) {
                ctx.tb_start += std::chrono::steady_clock::now() - parked_at;
            }
            state = State::Idle;
        }
        changed.notify_all();
    }

    std::chrono::steady_clock::time_point frozen_time() {
        std::lock_guard<std::mutex> lock(mutex);
        if (state != State::Parked) { throw std::logic_error("CPU snapshot barrier is not parked"); }
        return parked_at;
    }

    void stop() {
        std::lock_guard<std::mutex> lock(mutex);
        state = State::Stopped;
        requested.store(false, std::memory_order_release);
        changed.notify_all();
    }

    // Only reset before starting a CPU thread, after its previous thread has joined.
    void reset() {
        std::lock_guard<std::mutex> lock(mutex);
        if (state != State::Idle && state != State::Stopped) {
            throw std::logic_error("CPU snapshot barrier is still active");
        }
        state = State::Idle;
        requested.store(false, std::memory_order_release);
    }

private:
    enum class State { Idle, Requested, Parked, Releasing, Stopped };
    std::atomic<bool> requested{false};
    std::mutex mutex;
    std::condition_variable changed;
    State state = State::Idle;
    ClockPolicy clock_policy = ClockPolicy::Freeze;
    std::chrono::steady_clock::time_point parked_at{};
};

inline CpuBarrier cpu_barrier;

// Main thread must also quiesce audio and finish GPU work before accessing a full game snapshot.
class ParkedCpu {
public:
    explicit ParkedCpu(CpuBarrier& target, std::chrono::milliseconds timeout)
        : barrier(target.acquire(timeout) ? &target : nullptr) {}
    ParkedCpu(const ParkedCpu&) = delete;
    ParkedCpu& operator=(const ParkedCpu&) = delete;
    ~ParkedCpu() {
        if (barrier) { barrier->release(policy); }
    }
    explicit operator bool() const { return barrier != nullptr; }
    void clock(CpuBarrier::ClockPolicy value) { policy = value; }

private:
    CpuBarrier* barrier;
    CpuBarrier::ClockPolicy policy = CpuBarrier::ClockPolicy::Freeze;
};

}
