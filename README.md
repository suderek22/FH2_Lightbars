# PoliceLightbars 0.1.15 test build

PoliceLightbars adds amber and blue roof lightbars to the 2014 Alfa Romeo 4C
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
late, the fallback database must also include upgrade IDs 2038001 and 2038002.
The test runtime already has these IDs.

To build, run `work/Build.generated.cmd` from `work`, then run
`python BuildPack.py <path-to-stock-ALF_4C_14.zip> <FH6-installation>` from the
project directory. The build writes to `dist/0.1.15`.

The optional integration uses the MIT-licensed FH2 ANNA interface.
See https://github.com/qiangqiang101/FH2-ANNA.
The native FH2 light manager reference is https://github.com/qiangqiang101/FH2-Underglow.
