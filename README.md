# PoliceLightbars

Add an amber or blue flashing roof lightbar to 31 cars in Forza Horizon 2. Buy and fit either color from **Upgrades > Aero and Appearance > Hood** (called **Bonnet** in some locales). The lightbars flash in the garage and in free roam.

<img width="800" height="450" alt="fh2-lightbars" src="https://github.com/user-attachments/assets/30b700e5-7463-467a-99db-47d37af91202" />


## Requirements

- Forza Horizon 2 running in Azimuth.
- FH2 Mod Platform 2.9.1 or a compatible newer release.
- Offline play.
- FH2 ANNA is optional and adds a shortcut to the lighting toggle.

## Installation

1. Close Forza Horizon 2 and Azimuth.
2. If you installed a previous version with a car pack, move the old `fh2-cars/PoliceLightbars` or `fh2-cars/FH2-4CLightbars` folder outside `fh2-cars`. If you have the old `fh2-mods/FH2-4CLightbars.dll`, move it outside `fh2-mods` as well.
3. Download the current ZIP and extract it into the folder containing `azimuth.exe`. The DLL should be at `fh2-mods/PoliceLightbars.dll`. When updating from another DLL-only build, replace the existing DLL. [PoliceLightbars releases](https://github.com/suderek22/FH2_Lightbars/releases)
4. Launch FH2 and open **Hood** or **Bonnet** in the upgrade shop for a supported car. A previously fitted lightbar carries over because the upgrade IDs are the same.

## Lighting controls

- **Mod Platform** — Open **Pause > Settings > MODS > PoliceLightbars > Police lights**.
- **FH2 ANNA** — Open **Car > Lights** and select **Lightbar** to toggle the displayed On/Off state.

Both controls change the same setting. Turning the lights off stops the flashing while leaving the fitted lightbar on the roof. The setting is saved between sessions.

## Supported cars and compatibility

The lineup includes the 2014 Alfa Romeo 4C, the 2012 Dodge Charger SRT8, and 29 additional cars. See the [additional cars by game file name](ExtraCars.txt).

The DLL registers the upgrades and loads the lightbar assets over the existing game files. The download includes the DLL and requires no car ZIPs or `fh2-cars` folder. Mods that override the same car's `.carbin`, `Lights.bin`, or `LightPresets.bin` can conflict with PoliceLightbars. Using both on the same car requires a merged version of those files.

See the [changelog](CHANGELOG.md) for release details and verification status.
