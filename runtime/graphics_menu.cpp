#include "graphics_menu_row.hpp"

extern "C" bool RedPandaReadStyle() noexcept;
extern "C" bool RedPandaSaveStyle(bool panda) noexcept;

namespace {
// Graphics menu and scene update both run on the game thread.
bool& selected_style() noexcept
{
    static bool selected = RedPandaReadStyle();
    return selected;
}
}

extern "C" __declspec(dllexport) bool RedPandaSelectedStyle() noexcept
{
    return selected_style();
}

extern "C" __declspec(dllexport) void RedPandaMenuRow(red_panda::GraphicsMenuRow* row) noexcept
{
    if (row) *row = red_panda::character_style_row(selected_style());
}

extern "C" __declspec(dllexport) bool RedPandaConfirmMenuRow(int row) noexcept
{
    if (row != red_panda::character_style_id) return false;
    bool& selected = selected_style();
    if (RedPandaSaveStyle(!selected)) selected = !selected;
    return true;
}
