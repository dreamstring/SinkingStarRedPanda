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
    std::uint8_t draw_flag_33;  // Passed separately by the native row renderer.
    std::uint8_t padding[6];
};

static_assert(std::is_trivially_copyable_v<GraphicsMenuRow>);
static_assert(sizeof(GraphicsMenuRow) == 40);
static_assert(offsetof(GraphicsMenuRow, row_id) == 16);
static_assert(offsetof(GraphicsMenuRow, value) == 24);
static_assert(offsetof(GraphicsMenuRow, flags) == 32);

constexpr int character_style_id = 6;

constexpr int next_graphics_row(int current, int direction, std::uint32_t native_enabled)
{
    constexpr int count = character_style_id + 1;
    if (current < 0 || current >= count || (direction != 1 && direction != -1))
        return current;
    const auto enabled = native_enabled | (1u << character_style_id);
    auto candidate = current;
    for (int step = 0; step < count; ++step) {
        candidate = (candidate + direction + count) % count;
        if (enabled & (1u << candidate)) return candidate;
    }
    return current;
}

static_assert(next_graphics_row(0, -1, 0x3f) == character_style_id);
static_assert(next_graphics_row(character_style_id, 1, 0x3e) == 1);
static_assert(next_graphics_row(5, 1, 0) == character_style_id);

constexpr GraphicsMenuRow character_style_row(bool panda)
{
    const std::string_view key = panda ? "red_panda_character_style_panda"
                                       : "red_panda_character_style_original";
    return {static_cast<std::int64_t>(key.size()), key.data(), character_style_id, 0, -1.0, 1, 0, {}};
}

using DrawMenuRows = void (*)(void*, std::int64_t, const GraphicsMenuRow*,
                              int, int, const void*);

inline bool is_graphics_page(std::int64_t count, const GraphicsMenuRow* rows) {
    // The native settings pages share this renderer. Match the graphics page by its first localization key.
    std::string_view first;
    if (count > 0 && count <= character_style_id && rows && rows[0].key &&
        rows[0].key_length > 0 && rows[0].key_length <= 32)
        first = {rows[0].key, static_cast<std::size_t>(rows[0].key_length)};
    return first == "fullscreen_on" || first == "fullscreen_off";
}

inline void draw_character_graphics_menu(DrawMenuRows draw, void* context,
                                         std::int64_t count, const GraphicsMenuRow* rows,
                                         int layout, int selected, const void* color,
                                         bool panda)
{
    if (!is_graphics_page(count, rows)) {
        draw(context, count, rows, layout, selected, color);
        return;
    }
    std::array<GraphicsMenuRow, character_style_id + 1> visible;
    if (count) std::copy_n(rows, count, visible.begin());
    visible[count] = character_style_row(panda);
    draw(context, count + 1, visible.data(), layout, selected, color);
}
}
