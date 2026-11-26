#pragma once

#include <cstddef>
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

constexpr GraphicsMenuRow character_style_row(std::int32_t row_id, bool panda)
{
    const std::string_view key = panda ? "red_panda_character_style_panda"
                                       : "red_panda_character_style_original";
    return {static_cast<std::int64_t>(key.size()), key.data(), row_id, 0, -1.0, 1, {}};
}
}
