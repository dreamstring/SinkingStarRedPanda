#include <windows.h>
#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>

namespace fs = std::filesystem;

namespace {
using Paths = std::unordered_map<std::wstring, std::wstring>;

fs::path asset_directory()
{
    extern IMAGE_DOS_HEADER __ImageBase;
    HMODULE module{};
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCWSTR>(&asset_directory), &module))
        return {};
    std::vector<wchar_t> name(32768);
    const auto count = GetModuleFileNameW(module, name.data(), static_cast<DWORD>(name.size()));
    if (!count || count == name.size()) return {};
    return fs::path(name.data()).parent_path() / L"assets";
}

Paths index_assets()
{
    Paths paths;
    const auto root = asset_directory();
    if (root.empty()) return paths;
    for (const auto directory : {L"data", L"data-pc", L"data-common"}) {
        const auto folder = root / directory;
        if (!fs::is_directory(folder)) continue;
        for (const auto& entry : fs::recursive_directory_iterator(folder)) {
            if (entry.is_regular_file())
                paths.emplace(entry.path().lexically_relative(root).generic_wstring(),
                              entry.path().wstring());
        }
    }
    return paths;
}
}

// A null result delegates the original resource key to the game's catalog.
// Returned strings remain valid until the plugin is unloaded.
extern "C" __declspec(dllexport) const wchar_t* RedPandaAssetPath(
    const wchar_t* game_key, bool panda) noexcept
{
    if (!panda || !game_key) return nullptr;
    try {
        static const Paths paths = index_assets();
        const auto key = fs::path(game_key).generic_wstring();
        const auto found = paths.find(key);
        return found == paths.end() ? nullptr : found->second.c_str();
    } catch (...) {
        return nullptr;
    }
}
