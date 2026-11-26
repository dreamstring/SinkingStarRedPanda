#pragma once

#include <cstddef>
#include <algorithm>
#include <array>
#include <cstdint>
#include <string_view>
#include <type_traits>

namespace red_panda {
struct GraphicsMenuRow {
    std::int64_t key_length;
    const char* key;
    std::int32_t row_id;
    std::uint32_t reserved;
    double value;
    std::uint8_t flags;
    std::uint8_t padding[7];
};

static_assert(std::is_trivially_copyable_v<GraphicsMenuRow>);
static_assert(sizeof(GraphicsMenuRow) == 40);
static_assert(offsetof(GraphicsMenuRow, row_id) == 16);
static_assert(offsetof(GraphicsMenuRow, value) == 24);
static_assert(offsetof(GraphicsMenuRow, flags) == 32);

constexpr int character_style_id = 6;

constexpr int next_graphics_row(int current, int direction, std::uint32_t enabled)
{
    constexpr int count = character_style_id + 1;
    if (current < 0 || current >= count || (direction != 1 && direction != -1))
        return current;
    auto candidate = current;
    for (int step = 0; step < count; ++step) {
        candidate = (candidate + direction + count) % count;
        if (enabled & (1u << candidate)) return candidate;
    }
    return current;
}

constexpr GraphicsMenuRow character_style_row(bool panda)
{
    const std::string_view key = panda ? "red_panda_character_style_panda"
                                       : "red_panda_character_style_original";
    return {static_cast<std::int64_t>(key.size()), key.data(), character_style_id, 0, -1.0, 1, {}};
}

using DrawMenuRows = void (*)(void*, std::int64_t, const GraphicsMenuRow*,
                              int, int, const void*);

inline void draw_character_graphics_menu(DrawMenuRows draw, void* context,
                                         std::int64_t count, const GraphicsMenuRow* rows,
                                         int layout, int selected, const void* color,
                                         bool panda)
{
    if (count < 0 || count > character_style_id || (count && !rows)) {
        draw(context, count, rows, layout, selected, color);
        return;
    }
    std::array<GraphicsMenuRow, character_style_id + 1> visible;
    if (count) std::copy_n(rows, count, visible.begin());
    visible[count] = character_style_row(panda);
    draw(context, count + 1, visible.data(), layout, selected, color);
}
}
