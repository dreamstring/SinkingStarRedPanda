#pragma once

#include <cstddef>
#include <cstdint>
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
}
