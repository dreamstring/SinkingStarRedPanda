#include <windows.h>
#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>

namespace fs = std::filesystem;

namespace {
using Paths = std::unordered_map<std::wstring, std::wstring>;

fs::path plugin_directory()
{
    HMODULE module{};
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                            GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCWSTR>(&plugin_directory), &module))
        return {};
    std::vector<wchar_t> name(32768);
    const auto count = GetModuleFileNameW(module, name.data(), static_cast<DWORD>(name.size()));
    if (!count || count == name.size()) return {};
    return fs::path(name.data()).parent_path();
}

Paths index_assets()
{
    Paths paths;
    const auto directory_path = plugin_directory();
    if (directory_path.empty()) return paths;
    const auto root = directory_path / L"assets";
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

extern "C" __declspec(dllexport) bool RedPandaReadStyle() noexcept
{
    try {
        const auto directory = plugin_directory();
        if (directory.empty()) return false;
        const auto path = directory / L"appearance.cfg";
        HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE,
                                  nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file == INVALID_HANDLE_VALUE) return false;
        char bytes[2]{};
        DWORD count = 0;
        const bool panda = ReadFile(file, bytes, sizeof(bytes), &count, nullptr) && count == 1 && bytes[0] == '1';
        CloseHandle(file);
        return panda;
    } catch (...) { return false; }
}

extern "C" __declspec(dllexport) bool RedPandaSaveStyle(bool panda) noexcept
{
    try {
        const auto directory = plugin_directory();
        if (directory.empty()) return false;
        const auto path = directory / L"appearance.cfg";
        wchar_t temporary[MAX_PATH]{};
        if (!GetTempFileNameW(directory.c_str(), L"rps", 0, temporary)) return false;
        HANDLE file = CreateFileW(temporary, GENERIC_WRITE, 0, nullptr, TRUNCATE_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        bool saved = false;
        if (file != INVALID_HANDLE_VALUE) {
            const char value = panda ? '1' : '0';
            DWORD count = 0;
            saved = WriteFile(file, &value, 1, &count, nullptr) && count == 1 && FlushFileBuffers(file);
            CloseHandle(file);
        }
        if (saved && MoveFileExW(temporary, path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) return true;
        DeleteFileW(temporary);
        return false;
    } catch (...) { return false; }
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
