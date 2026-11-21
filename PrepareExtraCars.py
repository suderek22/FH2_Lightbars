from pathlib import Path
from zipfile import ZipFile
import sqlite3,sys,subprocess,json
import numpy as np
p=Path('FH2-4CLightbars').resolve(); w=p/'work'
sys.path.insert(0,'CarPackStudio')
from cps.model import load_model
r=next(Path(r'F:\fh2port-azimuth1.0').glob('Anthem*/Mount'))
names=(p/'ExtraCars.txt').read_text().split()
out={}
with sqlite3.connect('file:'+(r/'media/stripped/gamedbRC.slt').as_posix()+'?mode=ro',uri=True) as db:
 for name in names:
  try:
   body,=db.execute('select b.CarBodyID from Data_Car d join List_UpgradeCarBody b on b.Ordinal=d.Id and b.IsStock=1 where d.MediaName=? collate nocase',[name]).fetchone()
   assert not db.execute('select Id from List_UpgradeCarBodyHood where Id in (?,?)',[body+90,body+91]).fetchall()
   with ZipFile(r/'media/cars'/f'{name}.zip') as z:
    body_model=next(n for n in z.namelist() if n.lower().endswith('/platform/body_a.modelbin'))
    carbin=next(n for n in z.namelist() if n.lower()==f'{name}.carbin'.lower())
    stock=w/f'stock-{name}.carbin'
    stock.write_bytes(z.read(carbin))
    mesh=load_model(z.read(body_model))
    pts=np.concatenate([m.pos for m in mesh.meshes if any(x in m.name.lower() for x in ('lods0','lod0'))])
    center=pts[(abs(pts[:,0])<.53)&(abs(pts[:,2])<1.3)]
    roof=center[center[:,1]>center[:,1].max()-.045]
    zpos=float(np.median(roof[:,2]))
    span=center[(abs(center[:,2]-zpos)<.20)&(abs(center[:,0])>.22)]
    height=float(span[:,1].max() if len(span) else center[:,1].max())
    shift=[round(height-1.055,3),round(zpos+.16,3)]
   subprocess.run(['dotnet','exec','--runtimeconfig',str(w/'scene-tools/ForzaTech Studio.runtimeconfig.json'),str(w/'AddRoofUpgrades.exe'),str(w/'scene-tools/libs'),str(stock),str(w/'ALF_4C_14.carbin'),str(w/f'{name}.carbin'),str(body),name,*map(str,shift),str(body+90)],check=True)
   out[name]={'body':body,'offset':shift}
   print(name,body,shift,flush=True)
  except Exception as e: print('FAILED',name,str(e),flush=True)
if set(out) != set(names):
    raise SystemExit('At least one requested car failed; the previous placement manifest was retained.')
(p/'ExtraPlacements.json').write_text(json.dumps(out,indent=2)+'\n')
