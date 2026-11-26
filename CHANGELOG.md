# PoliceLightbars changelog

## 0.3.4

- Added optional LicencePlates 1.0.0 integration for all 31 supported cars. See [mod integrations](mods_integration.md).
- Refresh all car scene overrides before publishing the Hood upgrades or registering the other assets. When LicencePlates is missing or disabled, restore the regular Lightbars scenes and log the refresh.

## 0.3.3

- Removed the offline-only designation in FH2 Mod Platform.

## 0.3.2

- Apply the Hood upgrade database changes during mod initialization, before registering the car assets. This addresses a startup timing issue reported in 0.3.1, where previously fitted lightbars still worked but most supported cars did not show the upgrades in the garage.
- Verified that the SQL adds both upgrades for all 31 cars with their existing IDs. Garage visibility in-game remains unconfirmed for this build.

## 0.3.1

- Expanded the DLL-only installation to all 31 supported cars. The DLL registers overrides for the changed files through FH2 Mod Platform and requires no `fh2-cars` folder.
- Store identical asset payloads once in the DLL. Shared textures and materials are reused. Model files remain specific to each car because roof placement is baked into them.
- Retained the amber and blue upgrade names, the Mod Platform lighting setting, and the optional FH2 ANNA toggle.

## 0.3.0-preview.1

- Tested DLL-only installation on the 2014 Alfa Romeo 4C. The DLL embeds the 11 changed or added files and registers them as overrides for the stock car archive.

## 0.2.2 patch-only edition

- Added a smaller download that generates car archives locally from the installed game files.
- Added an optional merge with an existing replacement car archive. This preserves its scene edits and existing lighting records while appending the lightbar upgrades, attachments, and presets. A simulated license-plate overlay was verified.

## 0.2.2

- Enabled update checks through the PoliceLightbars GitHub repository.
- Marked the mod offline only in FH2 Mod Platform.

## 0.2.1

- Added amber and blue lightbars to 29 more cars, bringing the total to 31.

## 0.2.0

- Added the 2012 Dodge Charger SRT8, with roof placement and emitters positioned for its model.

## 0.1.x test builds

- Introduced amber and blue roof lightbars as Hood upgrades for the 2014 Alfa Romeo 4C.
- Added textures, flashing emitters, and reflected lighting in the garage and free roam, including daytime emitter visibility.
- Renamed the mod and DLL to PoliceLightbars.
- Added a lighting switch in FH2 Mod Platform and a single **Lightbar On / Off** toggle under **Car > Lights** when FH2 ANNA is installed.
