#include <windows.h>
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

extern "C" __declspec(dllexport) void RedPandaDrawGraphicsMenu(
    red_panda::DrawMenuRows draw, void* context, std::int64_t count,
    const red_panda::GraphicsMenuRow* rows, int layout, int selected,
    const void* color) noexcept
{
    red_panda::draw_character_graphics_menu(draw, context, count, rows,
                                            layout, selected, color, selected_style());
}

extern "C" __declspec(dllexport) void RedPandaDrawInstalledPage(
    void* context, std::int64_t count, const red_panda::GraphicsMenuRow* rows,
    int layout, int selected, const void* color) noexcept
{
    // This adapter is imported only by the fingerprinted Steam build.
    auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    auto draw = reinterpret_cast<red_panda::DrawMenuRows>(base + 0xb2250);
    RedPandaDrawGraphicsMenu(draw, context, count, rows, layout, selected, color);
}