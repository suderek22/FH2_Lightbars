from pathlib import Path
from zipfile import ZipFile
import hashlib, json, subprocess, sys
work = Path(__file__).resolve().parent
project = work.parent.parent
plate_cars = Path(sys.argv[1])
stock_cars = Path(sys.argv[2])
specs = json.loads((project/'dist/0.2.2-patch/patches/manifest.json').read_text())
reference = project/'dist/0.2.2/fh2-cars/PoliceLightbars/media/cars'
scenes = work/'merged'
scenes.mkdir(exist_ok=True)
rc = (work.parent/'031/LooseAssets.rc').read_text()
rows = []
for i, car in enumerate(sorted(specs), 900):
    patch = plate_cars/car/f'{car}.carbin.json'
    raw = patch.read_bytes()
    entry = specs[car]['scene']
    with ZipFile(stock_cars/f'{car}.zip') as archive:
        assert hashlib.sha256(archive.read(entry)).hexdigest() == json.loads(raw)['base_sha256'], car
    with ZipFile(reference/f'{car}.zip') as archive:
        source = scenes/entry
        source.write_bytes(archive.read(entry))
    merged = scenes/f'{i}.carbin'
    subprocess.run(['dotnet','exec','--runtimeconfig',str(work.parent/'scene-tools/ForzaTech Studio.runtimeconfig.json'),
                    str(work/'MergeScenes.exe'),str(work.parent/'scene-tools/libs'),str(source),str(patch),str(merged)],check=True)
    rc += f'{i} RCDATA "../034/merged/{i}.carbin"\n'
    rows.append(f'    {{{i}, "{car}", "{entry}", "{hashlib.sha256(raw).hexdigest()}"}},')
    if car == 'ALF_4C_14':
        baseline = (work/'4c-merged.carbin').read_bytes()
        print('4C matches preview:', baseline == merged.read_bytes(), flush=True)
(work/'Prototype.rc').write_text(rc)
(work/'PlateScenes.inc').write_text('\n'.join(rows)+'\n')
