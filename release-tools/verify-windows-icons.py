"""Compare PE RT_GROUP_ICON/RT_ICON bytes directly to the supplied ICO."""
from pathlib import Path
import argparse,struct,hashlib,json
import pefile
p=argparse.ArgumentParser();p.add_argument('files',type=Path,nargs='+');p.add_argument('--icon',type=Path,default=Path('windows/drilling-workbench-blue.ico'));args=p.parse_args()
raw=args.icon.read_bytes();reserved,kind,count=struct.unpack_from('<HHH',raw);assert (reserved,kind)==(0,1)
expected=[]
for i in range(count):
 width,height,colors,reserved,planes,bits,size,offset=struct.unpack_from('<BBBBHHII',raw,6+16*i)
 expected.append((width or 256,height or 256,raw[offset:offset+size]))
reports=[]
for file in args.files:
 pe=pefile.PE(str(file));resources={entry.id:entry for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries if entry.id is not None}
 images={}
 for entry in resources[3].directory.entries:
  language=entry.directory.entries[0];data=language.data.struct;images[entry.id]=pe.get_data(data.OffsetToData,data.Size)
 groups=[]
 for entry in resources[14].directory.entries:
  data=entry.directory.entries[0].data.struct;group=pe.get_data(data.OffsetToData,data.Size);_,kind,count=struct.unpack_from('<HHH',group);actual=[]
  for i in range(count):
   width,height,colors,reserved,planes,bits,size,identity=struct.unpack_from('<BBBBHHIH',group,6+14*i);image=images[identity];assert len(image)==size
   actual.append((width or 256,height or 256,image))
  matches=len(actual)==len(expected) and sorted((w,h,hashlib.sha256(b).hexdigest()) for w,h,b in actual)==sorted((w,h,hashlib.sha256(b).hexdigest()) for w,h,b in expected)
  groups.append({'group':entry.id,'matchesUploadedIcon':matches,'sizes':[[w,h] for w,h,_ in actual]})
 assert groups and groups[0]['matchesUploadedIcon'],str(file)+' first/default icon does not match'
 reports.append({'file':str(file),'defaultIconMatchesUploadedICO':True,'groups':groups,'fileSHA256':hashlib.sha256(file.read_bytes()).hexdigest()})
print(json.dumps({'sourceICO':str(args.icon),'sourceSHA256':hashlib.sha256(raw).hexdigest(),'verifiedPEIcons':reports,'nativeWindowsVisualCheckPerformed':False},ensure_ascii=False,indent=2))
