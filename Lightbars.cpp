#include <windows.h>
#include <bcrypt.h>
#pragma comment(lib, "bcrypt.lib")

#include <array>
#include <filesystem>
#include <fstream>
#include <string>

#include <atomic>
#include <cstdint>
#include <cstring>
#include <cstdio>

#include "fh2mod.h"
#include "fh2anna.h"

namespace {
constexpr std::uintptr_t updateRva = 0x13B6A90;
constexpr unsigned char updateCode[] = {0x48, 0x8b, 0xc4, 0x55, 0x56, 0x57, 0x41, 0x54};
constexpr std::uintptr_t intensityRva = 0x10F0550;
constexpr unsigned char intensityCode[] = {
    0x48, 0x83, 0xec, 0x28, 0x44, 0x8b, 0xc2, 0x4c, 0x8b, 0xd1, 0x83, 0xfa, 0xff
};
constexpr float bankRanges[] = {8.0625f, 8.125f, 8.1875f, 8.25f};
constexpr wchar_t section[] = L"Lighting";
constexpr wchar_t enabledKey[] = L"PoliceLights";
constexpr char settingKey[] = "PoliceLights";
constexpr char annaMenuKey[] = "policelightbars.lightbar";

const FH2ModApi* platform = nullptr;
FH2Mod* plugin = nullptr;
wchar_t ini[MAX_PATH]{};
std::atomic<bool> enabled{true};
std::atomic<unsigned> reportedBanks{0};


using SetIntensity = void (*)(void*, std::uint32_t, float);
SetIntensity originalIntensity = nullptr;
using UpdateLights = void (*)(void*);
UpdateLights originalUpdate = nullptr;

struct Pool {
    const unsigned char* begin;
    const unsigned char* end;
    const unsigned char* capacity;
};

const unsigned char* entry(const Pool& pool, std::uint32_t index, std::size_t stride) {
    const auto first = reinterpret_cast<std::uintptr_t>(pool.begin);
    const auto last = reinterpret_cast<std::uintptr_t>(pool.end);
    if (!first || last < first || last - first > stride * 100000u ||
        (last - first) % stride || index >= (last - first) / stride)
        return nullptr;
    return pool.begin + index * stride;
}

// LightManager's handle table points through the beam record to its preset.
// Only the four presets shipped in the 4C archive have these range/color pairs.
struct RoofLight {
    int bank = -1;
    const unsigned char* beam = nullptr;
    const unsigned char* preset = nullptr;
    const unsigned char* beams = nullptr;
    std::uint32_t glow = ~0u;
};

RoofLight roofLight(void* manager, std::uint32_t handle) {
    __try {
        const auto* object = static_cast<const unsigned char*>(manager);
        const auto* mapping = entry(*reinterpret_cast<const Pool*>(object + 0x28), handle, 24);
        const auto* beams = *reinterpret_cast<const unsigned char* const*>(object + 0x08);
        if (!mapping || !beams) return {};
        const auto* beam = entry(*reinterpret_cast<const Pool*>(beams),
                                 *reinterpret_cast<const std::uint32_t*>(mapping), 0x40);
        if (!beam) return {};
        const auto* preset = entry(*reinterpret_cast<const Pool*>(beams + 0x38),
                                   *reinterpret_cast<const std::uint32_t*>(beam + 0x30), 0xC0);
        if (!preset) return {};
        const float range = *reinterpret_cast<const float*>(preset + 0x60);
        const auto* rgb = reinterpret_cast<const float*>(preset + 0x50);
        for (int bank = 0; bank < 4; ++bank) {
            if (range != bankRanges[bank]) continue;
            if (bank < 2 ? (rgb[0] > 0.6f && rgb[2] < 0.1f)
                         : (rgb[2] > 0.6f && rgb[0] < 0.1f))
                return {bank, beam, preset, beams, *reinterpret_cast<const std::uint32_t*>(mapping + 4)};
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return {};
    }
    return {};
}

float* roofChannels(void* presentation) {
    __try {
        auto* object = static_cast<unsigned char*>(presentation);
        const auto* context = *reinterpret_cast<const unsigned char* const*>(object + 0x10);
        const auto* asset = *reinterpret_cast<const unsigned char* const*>(object + 0x1278);
        if (!context || !asset) return nullptr;
        auto* manager = *reinterpret_cast<void* const*>(context + 0x380);
        if (!manager) return nullptr;
        const auto& instances = *reinterpret_cast<const Pool*>(asset + 0x4BE0);
        for (std::uint32_t index = 0; index < 256; ++index) {
            const auto* slot = entry(instances, index, sizeof(void*));
            if (!slot) break;
            const auto* instance = *reinterpret_cast<const unsigned char* const*>(slot);
            if (!instance) continue;
            const auto type = *reinterpret_cast<const std::uint16_t*>(instance + 4);
            if (type != 0x31 && type != 0x32) continue;
            const auto handle = *reinterpret_cast<const std::uint32_t*>(instance + 0x50);
            if (roofLight(manager, handle).bank >= 0)
                return reinterpret_cast<float*>(object + 0x1B70) + 0x31;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return nullptr;
    }
    return nullptr;
}

void updateLights(void* presentation) {
    auto* channels = roofChannels(presentation);
    if (!channels) {
        originalUpdate(presentation);
        return;
    }
    const auto beat = (GetTickCount64() / 95) % 8;
    const bool flash = enabled.load(std::memory_order_relaxed) && beat % 2 == 0;
    // Keep the dedicated roof channels available to the material pass after the light update.
    channels[0] = flash && beat < 4 ? 1.0f : 0.0f;
    channels[1] = flash && beat >= 4 ? 1.0f : 0.0f;
    originalUpdate(presentation);
}

void removeDaylightCutoff(const RoofLight& light) {
    // Only write to the custom preset, then ask FH2 to refresh the GPU copy.
    __try {
        auto* threshold = reinterpret_cast<float*>(const_cast<unsigned char*>(light.preset) + 0x9C);
        if (threshold[0] != 0.0f || threshold[1] != 0.0f) {
            threshold[0] = 0.0f;
            threshold[1] = 0.0f;
            *(const_cast<unsigned char*>(light.beams) + 0x100) = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

void setIntensity(void* manager, std::uint32_t handle, float nativeValue) {
    if (nativeValue <= 0.0f) {
        originalIntensity(manager, handle, nativeValue);
        return;
    }
    const auto light = roofLight(manager, handle);
    if (light.bank >= 0) removeDaylightCutoff(light);
    originalIntensity(manager, handle, nativeValue);
    if (light.bank < 0) return;
    const unsigned bit = 1u << light.bank;
    if ((reportedBanks.load(std::memory_order_relaxed) & bit) ||
        (reportedBanks.fetch_or(bit, std::memory_order_relaxed) & bit)) return;
    float values[4]{};
    __try {
        std::memcpy(values, light.beam + 0x10, sizeof values);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    char message[180];
    std::snprintf(message, sizeof message,
                  "Roof bank %d lit by FH2: world=(%.2f %.2f %.2f), intensity=%.2f, glow=%u.",
                  light.bank, values[1], values[2], values[3], values[0], light.glow);
    platform->log(plugin, message);
}

void setEnabled(void*, const char*, int value) {
    enabled.store(value != 0, std::memory_order_relaxed);
    if (ini[0]) WritePrivateProfileStringW(section, enabledKey, value ? L"1" : L"0", ini);
    platform->log(plugin, value ? "Police lights on." : "Police lights off.");
}

void chooseInAnna(void*, const char*) {
    const int value = enabled.load(std::memory_order_relaxed) ? 0 : 1;
    setEnabled(nullptr, settingKey, value);
    platform->set_setting(plugin, settingKey, value);
}

const char* annaLightbarLabel(void*, const char*) {
    // Like ANNA's Headlights row, show the action that selecting the row takes.
    return enabled.load(std::memory_order_relaxed) ? "Lightbar Off" : "Lightbar On";
}

DWORD WINAPI installAnna(void*) {
    if (!platform->wait_for_mods(60000)) return 0;
    const auto* anna = static_cast<const FH2AnnaApi*>(platform->get_interface(FH2ANNA_INTERFACE, 4));
    if (!anna || !anna->add_entry) return 0;
    FH2AnnaEntry row{};
    row.size = sizeof(row);
    row.key = annaMenuKey;
    row.parent = "car.lights";
    row.label = "Lightbar On";
    row.on_choose = chooseInAnna;
    row.label_now = annaLightbarLabel;
    row.stays_open = 1;
    if (anna->add_entry(&row))
        platform->log(plugin, "Registered ANNA Car > Lights > Lightbar toggle.");
    else
        platform->log(plugin, "Could not register the Lightbar toggle in ANNA.");
    return 0;
}

void loadSettings(const wchar_t* directory) {
    if (!directory || swprintf_s(ini, L"%ls\\fh2-mods\\PoliceLightbars.ini", directory) < 0) {
        ini[0] = L'\0';
        return;
    }
    const auto value = GetPrivateProfileIntW(section, enabledKey, 2, ini);
    if (value != 2) {
        enabled.store(value != 0, std::memory_order_relaxed);
        return;
    }
    wchar_t legacy[MAX_PATH]{};
    if (swprintf_s(legacy, L"%ls\\fh2-mods\\FH2-4CLightbars.ini", directory) < 0) return;
    const auto previous = GetPrivateProfileIntW(section, enabledKey, 2, legacy);
    if (previous == 2) return;
    enabled.store(previous != 0, std::memory_order_relaxed);
    WritePrivateProfileStringW(section, enabledKey, previous ? L"1" : L"0", ini);
}

DWORD WINAPI installLights(void*) {
    auto* game = static_cast<unsigned char*>(platform->wait_for_code(60000));
    if (!game || std::memcmp(game + intensityRva, intensityCode, sizeof intensityCode) != 0 ||
        std::memcmp(game + updateRva, updateCode, sizeof updateCode) != 0) {
        platform->log(plugin, "Police light control unavailable on this game build.");
        return 0;
    }
    if (!platform->hook_function(plugin, "Position police roof lights through car presentation", game + updateRva,
                                 reinterpret_cast<void*>(updateLights), reinterpret_cast<void**>(&originalUpdate)) ||
        !platform->hook_function(plugin, "Observe positioned police roof lights", game + intensityRva,
                                 reinterpret_cast<void*>(setIntensity), reinterpret_cast<void**>(&originalIntensity)) ||
        !platform->enable_hooks(plugin, nullptr)) {
        platform->disable_hooks(plugin, nullptr);
        platform->log(plugin, "Could not enable police light control.");
        return 0;
    }
    platform->log(plugin, "Watching for native amber and blue roof-light presets.");
    return 0;
}
}

namespace {
struct PlateScene {
    WORD resource;
    const char* car;
    const char* file;
    const char* patchHash;
};

constexpr PlateScene plateScenes[] = {
#include "PlateScenes.inc"
};

bool licencePlatesListed(const std::filesystem::path& mods) {
    std::ifstream order(mods / "loadorder.txt");
    std::string line;
    while (std::getline(order, line)) {
        const auto first = line.find_first_not_of(" \t\r");
        if (first == std::string::npos) continue;
        const auto last = line.find_last_not_of(" \t\r");
        if (_stricmp(line.substr(first, last - first + 1).c_str(), "LicencePlates") == 0)
            return true;
    }
    return false;
}

bool patchMatches(const std::filesystem::path& path, const char* expected, BCRYPT_ALG_HANDLE sha256) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    const auto size = input.tellg();
    if (size <= 0 || size > 1024 * 1024) return false;
    std::string bytes(static_cast<size_t>(size), '\0');
    if (!input.seekg(0).read(bytes.data(), static_cast<std::streamsize>(bytes.size()))) return false;
    std::array<UCHAR, 32> digest{};
    if (BCryptHash(sha256, nullptr, 0, reinterpret_cast<PUCHAR>(bytes.data()),
                   static_cast<ULONG>(bytes.size()), digest.data(), static_cast<ULONG>(digest.size())) != 0)
        return false;
    constexpr char hex[] = "0123456789abcdef";
    for (size_t i = 0; i < digest.size(); ++i) {
        if (expected[i * 2] != hex[digest[i] >> 4] || expected[i * 2 + 1] != hex[digest[i] & 15])
            return false;
    }
    return true;
}

std::array<bool, std::size(plateScenes)> selectPlateScenes(const wchar_t* azimuth) {
    std::array<bool, std::size(plateScenes)> selected{};
    if (!azimuth) return selected;
    const auto mods = std::filesystem::path(azimuth) / "mods" / "Forza Horizon 2";
    const auto plate = mods / "LicencePlates";
    std::error_code error;
    if (!licencePlatesListed(mods) || !std::filesystem::is_regular_file(plate / "plugins" / "PlateLight.dll", error))
        return selected;
    BCRYPT_ALG_HANDLE sha256 = nullptr;
    if (BCryptOpenAlgorithmProvider(&sha256, BCRYPT_SHA256_ALGORITHM, nullptr, 0) != 0) {
        platform->log(plugin, "LicencePlates: SHA-256 unavailable. Using regular Lightbars scenes.");
        return selected;
    }
    for (size_t i = 0; i < selected.size(); ++i) {
        const auto& scene = plateScenes[i];
        const auto patch = plate / "media" / "cars" / scene.car / (std::string(scene.file) + ".json");
        selected[i] = patchMatches(patch, scene.patchHash, sha256);
        if (!selected[i]) {
            const auto message = std::string("LicencePlates: no matching patch for ") + scene.car + ". Using the regular Lightbars scene.";
            platform->log(plugin, message.c_str());
        }
    }
    BCryptCloseAlgorithmProvider(sha256, 0);
    unsigned count = 0;
    for (bool match : selected) count += match;
    char message[100]{};
    std::snprintf(message, sizeof(message), "LicencePlates: selected %u combined car scene(s).", count);
    platform->log(plugin, message);
    return selected;
}
}

FH2MOD_EXPORT int fh2mod_init(const FH2ModApi* api) {
    if (!api || api->api_version < 11) return 1;
    FH2ModInfo info{};
    info.size = sizeof(info);
    info.name = "PoliceLightbars";
    info.version = "0.3.4";
    info.description = "Adds amber and blue roof lightbars to 31 supported cars. Use Police lights to switch flashing on or off.";
    info.platform_version = "2.9.1";
    info.github_repo = "suderek22/FH2_Lightbars";
    info.offline_only = 0;
    plugin = api->register_mod(&info);
    if (!plugin) return 1;
    platform = api;
    loadSettings(api->azimuth_dir);
    FH2Setting setting{};
    setting.size = sizeof(setting);
    setting.key = settingKey;
    setting.label = "Police lights";
    setting.description = "Flash the roof lightbar fitted to a supported car.";
    setting.value = enabled.load() ? 1 : 0;
    setting.on_change = setEnabled;
    api->add_setting(plugin, &setting);
    HMODULE module = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           reinterpret_cast<LPCWSTR>(&fh2mod_init), &module))
        return 1;
    const struct { WORD resource; const char* path; } overrides[] = {
#include "LooseAssets.inc"
    };
    api->add_sql(plugin, R"SQL(
INSERT OR IGNORE INTO List_PartManufacturer (Id,PartManufacturer,LogoPath) VALUES (7101,'_&1568995346','decal146'),(7102,'_&1568995347','decal146');
INSERT OR IGNORE INTO List_UpgradeCarBodyHood (Id,CarBodyID,Level,IsStock,Sequence,ManufacturerId,PartsStringId,MassDiff,WeightDistDiff,DragScale,WindInstabilityScale,Price,RequiresGraphics)
SELECT stock.CarBodyID + variant.Offset, stock.CarBodyID, 1, 0, variant.Sequence, variant.ManufacturerId, stock.PartsStringId, stock.MassDiff, stock.WeightDistDiff, stock.DragScale, stock.WindInstabilityScale, 100, 1
FROM List_UpgradeCarBodyHood stock
CROSS JOIN (SELECT 1 AS Offset, 2 AS Sequence, 7101 AS ManufacturerId UNION ALL SELECT 2, 3, 7102) variant
WHERE stock.CarBodyID IN (2038000, 1422000) AND stock.Id=stock.CarBodyID AND stock.IsStock=1;
INSERT OR IGNORE INTO List_UpgradeCarBodyHood (Id,CarBodyID,Level,IsStock,Sequence,ManufacturerId,PartsStringId,MassDiff,WeightDistDiff,DragScale,WindInstabilityScale,Price,RequiresGraphics)
SELECT stock.CarBodyID + variant.UpgradeDelta, stock.CarBodyID, 1, 0, variant.UpgradeDelta, variant.ManufacturerId, stock.PartsStringId, stock.MassDiff, stock.WeightDistDiff, stock.DragScale, stock.WindInstabilityScale, 100, 1
FROM List_UpgradeCarBodyHood stock
CROSS JOIN (SELECT 90 AS UpgradeDelta, 7101 AS ManufacturerId UNION ALL SELECT 91, 7102) variant
WHERE stock.CarBodyID IN (1115000, 2180000, 1220000, 1388000, 1350000, 1626000, 1419000, 2177000, 1620000, 1131000, 1460000, 2155000, 1345000, 2108000, 1522000, 2110000, 1221000, 1658000, 1627000, 1525000, 1202000, 1009000, 2002000, 445000, 2293000, 1060000, 2393000, 1231000, 2156000) AND stock.Id=stock.CarBodyID AND stock.IsStock=1;
)SQL");
    api->apply_database(plugin);
    const auto plates = selectPlateScenes(api->azimuth_dir);
    for (const auto& entry : overrides) {
        WORD id = entry.resource;
        const char* extension = std::strrchr(entry.path, '.');
        if (extension && std::strcmp(extension, ".carbin") == 0) {
            const char* file = std::strrchr(entry.path, '/') + 1;
            for (size_t i = 0; i < plates.size(); ++i) {
                if (plates[i] && _stricmp(file, plateScenes[i].file) == 0) {
                    id = plateScenes[i].resource;
                    break;
                }
            }
        }
        HRSRC resource = FindResourceW(module, MAKEINTRESOURCEW(id), MAKEINTRESOURCEW(10));
        HGLOBAL loaded = resource ? LoadResource(module, resource) : nullptr;
        const void* data = loaded ? LockResource(loaded) : nullptr;
        if (!data || !api->set_file(plugin, entry.path, data, SizeofResource(module, resource))) {
            api->clear_file(plugin, nullptr);
            api->clear_sql(plugin);
            api->apply_database(plugin);
            api->log(plugin, entry.path);
            api->log(plugin, "Failed to register lightbar assets. Cleared this mod's file overrides.");
            return 1;
        }
    }
    api->log(plugin, "Lightbar file overrides registered for 31 cars.");
    api->set_string(plugin, "List_PartManufacturer.str", 0xF812, L"Amber Lightbar");
    api->set_string(plugin, "List_PartManufacturer.str", 0xF813, L"Blue Lightbar");
    if (HANDLE thread = CreateThread(nullptr, 0, installAnna, nullptr, 0, nullptr))
        CloseHandle(thread);
    if (HANDLE thread = CreateThread(nullptr, 0, installLights, nullptr, 0, nullptr))
        CloseHandle(thread);
    return 0;
}
