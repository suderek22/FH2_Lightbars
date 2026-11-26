# PoliceLightbars mod integrations

## LicencePlates 1.0.0

PoliceLightbars 0.3.4 integrates with LicencePlates 1.0.0 by Philipp55112, installed through FH2 Extra Options. The integration covers all 31 cars supported by PoliceLightbars. Each mod continues to load through its own loader. Install and enable LicencePlates in Extra Options and install PoliceLightbars in FH2 Mod Platform, then restart the game.

### Why the mods need a combined scene

Each car's `.carbin` describes its model attachments and upgrade groups. LicencePlates supplies an Extra Options `fh2-carbin-patch` JSON file per car. The patch adds HZN plate model records to the relevant part or upgrade group. PoliceLightbars supplies a loose `.carbin` override through FH2 Mod Platform because its roof bars need their own Hood upgrade records. With both mods active, the car can resolve to the Lightbars scene without the plate entries that Extra Options adds to the stock scene. The combined scene gives the game one file containing both sets of records.

### How the combined scenes are built

1. Start with the matching stock car archive, the regular PoliceLightbars scene, and the installed LicencePlates JSON patch. Verify that the stock scene's SHA-256 equals the patch's `base_sha256` and that the patch declares format `fh2-carbin-patch`, version 1, and the matching media name.
2. Read the Lightbars scene with ForzaTools and round-trip it before changing anything. The original binary must be reproduced byte for byte.
3. For a part-level merge, append the plate model to the existing non-upgradable part. For an upgrade-group merge, append it as a shared model and preserve the exact upgrade IDs listed in the patch. This retains the plate placement on the relevant stock and aftermarket parts.
4. Copy the model path, GUID, transform, LOD mask, bone, draw groups, material indices, AO mapping and render flags from each supported plate record. Check that each GUID is new within its target, each model points to the expected per-car HZN directory, and each group association refers to an existing upgrade. This release handles the records used by the verified LicencePlates 1.0.0 patches.
5. Reopen each result and verify that the Lightbars Hood mappings survived. Remove the inserted HZN records from the reopened scene and reserialize it. The result must exactly match the original Lightbars scene. The release adds 42 plate records across 31 scenes. The combined 4C scene matches the in-game-tested prototype byte for byte.
6. Embed the combined scenes as resources in PoliceLightbars.dll. The DLL also contains the regular Lightbars scenes for use without LicencePlates. The build scripts are under `work/034`.

### How the DLL selects a scene

At FH2 Mod Platform initialization, Lightbars looks under `mods/Forza Horizon 2` next to `azimuth.exe`. It checks `loadorder.txt` for an active `LicencePlates` entry and checks for `LicencePlates/plugins/PlateLight.dll`. Extra Options must also be enabled and able to load the plate mod.

For each supported car, Lightbars hashes the installed `LicencePlates/media/cars/<car>/<car>.carbin.json`. A matching hash selects the corresponding combined scene. If the patch is missing or has changed, that car uses the regular Lightbars scene and the reason is recorded in `fh2-mods/platform.log`. An edit that only changes JSON formatting also changes the hash. The lookup is per car, so a changed patch for one car does not affect the rest. With LicencePlates absent or unlisted, every car uses its regular Lightbars scene.

The DLL registers the selected scene at the usual `cars/<car>/<car>.carbin` override path. This selection runs at startup. The DLL refreshes all 31 scene overrides before publishing the Hood upgrades or registering other assets. With LicencePlates missing or disabled, the log reports that it is refreshing the regular scenes. Restart Azimuth after enabling, disabling, or updating LicencePlates.

### Which mod supplies each feature

| Feature | Provider |
| --- | --- |
| Hood upgrade rows, roof models, flash presets and emitters | PoliceLightbars |
| Combined scene for a supported car with a matching plate patch | PoliceLightbars |
| Plate meshes, materials, textures and shared plate assets | Installed LicencePlates via Extra Options |
| Plate editor, personalized plate, removal and plate lamp behavior | Installed LicencePlates and its PlateLight plugin |

The installed LicencePlates version contains no replacements for `Lights.bin` or `LightPresets.bin`, so those files continue to come from Lightbars for the supported cars. The integration does not modify the LicencePlates folder or the stock game archives. The download remains DLL-only and requires no car ZIPs.

### Verification and troubleshooting

With the verified LicencePlates patches enabled, look for `LicencePlates: selected 31 combined car scene(s).` in `fh2-mods/platform.log`. Check that Extra Options loaded `PlateLight.dll` in `FH2_ExtraOptions.log`. If a car is logged as using the regular Lightbars scene, check that its patch is the matching release file. Another mod overriding the same scene can still conflict.

The 4C prototype was confirmed in-game. All 31 production scenes passed the binary checks above. In-game checks on the expanded lineup should cover both lightbar colors, plate editing and removal, bumper-specific plate placement, and plate lamps and roof flashes operating together.

## FH2 ANNA

When FH2 ANNA is installed, select **Car > Lights > Lightbar** to toggle flashing. This controls the same saved setting as **Police lights** in FH2 Mod Platform. The LicencePlates integration does not change either control.
