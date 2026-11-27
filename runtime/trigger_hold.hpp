#pragma once
#include <cstdint>

struct TriggerHold {
    bool holding = false;
    bool armed = false;
    std::uint64_t start = 0;

    constexpr bool update(unsigned left, unsigned right, std::uint64_t now) {
        if (left < 180 || right < 180) holding = false;
        if (left < 60 && right < 60) armed = true;
        if (!armed || left < 220 || right < 220) return false;
        if (!holding) { holding = true; start = now; }
        if (now - start < 800) return false;
        armed = false;
        return true;
    }
};

constexpr bool test_trigger_hold() {
    TriggerHold t;
    return !t.update(255,255,0) && !t.update(0,0,1) &&
           !t.update(255,0,100) && !t.update(255,255,200) &&
           !t.update(255,255,999) && t.update(255,255,1000) &&
           !t.update(255,255,2000) && !t.update(0,255,2200) &&
           !t.update(255,255,3200) && !t.update(0,0,3400) &&
           !t.update(255,255,3500) && t.update(255,255,4300);
}
static_assert(test_trigger_hold());
