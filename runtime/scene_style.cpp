#include <windows.h>
#include <cstdint>
#include <cstring>
#include <string_view>

namespace {
struct Name {
    std::int64_t length;
    const char* text;
};
struct Appearance {
    Name original;
    Name panda;
};
#define ROLE(s) {{sizeof(s)-1, s}, {sizeof("red_panda_" s)-1, "red_panda_" s}}
constexpr Appearance appearances[] = {
    ROLE("warrior"), ROLE("warrior_alt"), ROLE("thief"), ROLE("thief_alt"),
    ROLE("wizard"), ROLE("cleric"), ROLE("cleric_alt"), ROLE("bard"),
    ROLE("druid"), ROLE("castaway"), ROLE("castaway_alt"), ROLE("moonman"),
    ROLE("moonman_alt"), ROLE("trader"), ROLE("trader_alt"), ROLE("queen")
};
#undef ROLE

bool equal(const Name& left, const Name& right) {
    return left.length == right.length && left.text &&
           std::memcmp(left.text, right.text, static_cast<size_t>(right.length)) == 0;
}
template<typename T>
T field(const void* object, size_t offset) {
    T value;
    std::memcpy(&value, static_cast<const char*>(object)+offset, sizeof(value));
    return value;
}
struct EntitySlot {
    std::uint32_t state;
    std::uint32_t reserved;
    void* entity;
};
static_assert(sizeof(EntitySlot)==16);
using SelectMesh = void(*)(void*,void*,const Name*);
}

// Class lookup accepts this length-prefixed name. Rendering retains the actual mesh.
extern "C" __declspec(dllexport) const Name* RedPandaProfessionName(const Name* name) noexcept {
    if (name)
        for (const auto& appearance : appearances)
            if (equal(*name,appearance.panda)) return &appearance.original;
    return name;
}

// Called on the game thread when a scene needs the selected appearance applied.
extern "C" __declspec(dllexport) int RedPandaApplyScene(
    void* context, void* world, const void* guyType, SelectMesh selectMesh, bool panda) noexcept {
    if (!context || !world || !guyType || !selectMesh || field<void*>(context,0x90)!=world) return -1;
    const auto count=field<std::int64_t>(world,0x3c0);
    const auto slots=field<EntitySlot*>(world,0x3c8);
    if (count<0 || (count && !slots)) return -1;
    int changed=0;
    for (std::int64_t i=0;i<count;++i) {
        const auto& slot=slots[i];
        if (slot.state<2 || !slot.entity || field<void*>(slot.entity,0x108)!=guyType) continue;
        const auto mesh=field<const Name*>(slot.entity,0x88);
        if (!mesh) continue;
        for (const auto& appearance : appearances) {
            const auto& from=panda ? appearance.original : appearance.panda;
            if (!equal(*mesh,from)) continue;
            const auto& to=panda ? appearance.panda : appearance.original;
            selectMesh(context,slot.entity,&to);
            const auto result=field<const Name*>(slot.entity,0x88);
            if (!result || !equal(*result,to)) return -1;
            ++changed;
            break;
        }
    }
    return changed;
}

extern "C" bool RedPandaSelectedStyle() noexcept;

extern "C" __declspec(dllexport) void RedPandaUpdateInstalledScene(
    void* context, void* world, unsigned char mode, std::uintptr_t flags, void* result) noexcept
{
    const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    using Update = void(*)(void*, void*, unsigned char, std::uintptr_t, void*);
    reinterpret_cast<Update>(base + 0x285d70)(context, world, mode, flags, result);
    RedPandaApplyScene(context, world, reinterpret_cast<const void*>(base + 0x6a8bf0),
                       reinterpret_cast<SelectMesh>(base + 0x199ac0), RedPandaSelectedStyle());
}

extern "C" __declspec(dllexport) void RedPandaClassifyInstalledProfession(
    const Name* mesh, unsigned char* profession) noexcept
{
    using Classify = void(*)(const Name*, unsigned char*);
    const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(nullptr));
    reinterpret_cast<Classify>(base + 0x219a20)(RedPandaProfessionName(mesh), profession);
}
