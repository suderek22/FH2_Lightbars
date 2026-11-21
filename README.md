# PoliceLightbars 0.2.1 test build

<img width="800" height="450" alt="fh2-lightbars" src="https://github.com/user-attachments/assets/676b2024-a58c-4da5-b3ca-4b2a7970f484" />

PoliceLightbars adds amber and blue roof lightbars to 31 cars
in offline Forza Horizon 2 on Azimuth with FH2 Mod Platform 2.9.1.

With the game closed, extract `fh2-mods` and `fh2-cars` into the Azimuth folder.
When upgrading, move `fh2-mods/FH2-4CLightbars.dll` and
`fh2-cars/FH2-4CLightbars` outside those folders before launching. The upgrade
IDs are the same, so a fitted lightbar carries over. The DLL migrates the old
on/off setting on the first launch if `PoliceLightbars.ini` has no saved value.

Switch the bar from **Pause > Settings > MODS > PoliceLightbars > Police lights**.
With FH2 ANNA installed, **Car > Lights > Lightbar On / Off** toggles the same
setting. The selected state is saved in `fh2-mods/PoliceLightbars.ini`.

If testing with an existing 4C in a runtime where the car-pack database loads
late, the fallback database must also include the fitted lightbar upgrade IDs (2038001/2038002 for the 4C and 1422001/1422002 for the Charger).
The test runtime already has these IDs.

To regenerate the Charger scene, run `BuildChargerScene.ps1 -ChargerArchive <stock-zip> -StudioDirectory <ForzaTech-Studio-folder>`. The script verifies that the stock scene round-trips before adding the upgrades. Run `python PrepareExtraCars.py` to regenerate the additional test scenes using that same compiled scene tool. Then run `work/Build.generated.cmd` from `work` and run
`python BuildPack.py <path-to-stock-ALF_4C_14.zip> <FH6-installation>` from the
project directory. The build writes to `dist/0.2.1`.

The optional integration uses the MIT-licensed FH2 ANNA interface.
See https://github.com/qiangqiang101/FH2-ANNA.
The native FH2 light manager reference is https://github.com/qiangqiang101/FH2-Underglow.

The Charger bar is centered laterally and placed 25 cm higher and 14 cm rearward relative to the 4C model coordinates. Its emitter positions use the same offset. The Charger placement is an estimate for the first in-game fit check.

The 29 new placements are estimated from their stock roof meshes. Their model-space offsets are listed in ExtraPlacements.json. Existing hood upgrades remain available.
