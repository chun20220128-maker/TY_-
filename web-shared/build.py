from pathlib import Path
import json,shutil,zipfile,hashlib
from sanitize import application
root=Path(__file__).resolve().parent.parent;src=root/'web-shared/src';out=root/'build/web-shared/site';shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True,exist_ok=True);(out/'protected').mkdir(exist_ok=True)
records=json.loads((root/'data/history-seed.json').read_text(encoding='utf-8'))
private_strings={h.get(k,'') for h in records for k in ['project','vendor']}
text=application((root/'index.html').read_text(encoding='utf-8'),private_strings)
text=text.replace('已載入內建 14 案／322 筆。','目前保留畫面中的參考資料。').replace('內建 14 案歷史單價仍可查閱。','請確認共用單價連線。')
text=text.replace("result.storage!=='sqlite'","!['sqlite','cloudflare-d1'].includes(result.storage)")
text=text.replace('互動原型 v0.2<br>資料儲存在此瀏覽器<br>請匯出備份保存工作內容','公司網頁版<br>歷史單價全公司共用<br>專案請自行匯出備份').replace('第二版互動原型','公司網頁版').replace('本機自動儲存','共用單價自動保存')
text=text.replace('歷史單價合併保留；相同紀錄以目前資料庫為準，修改單價請匯入 CSV。','共用歷史單價不會被專案備份覆蓋；歷史單價請另以 CSV 匯入。')
first=text.index('<script');text=text[:first]+'<script>\n'+(src/'adapter-start.js').read_text()+'\n</script>'+text[first:]
text=text.replace('</html>','<script>\n'+(src/'adapter-end.js').read_text()+'\n</script></html>')
(out/'protected/app.bundle').write_text(text,encoding='utf-8');(out/'protected/history-seed.json').write_text('[]');shutil.copyfile(src/'index.html',out/'index.html');shutil.copyfile(src/'setup.html',out/'protected/setup.bundle');shutil.copyfile(src/'worker.js',out/'_worker.js');shutil.copyfile(root/'windows/drilling-workbench-blue.ico',out/'favicon.ico')
(out/'_routes.json').write_text(json.dumps({'version':1,'include':['/*'],'exclude':[]}));(out/'robots.txt').write_text('User-agent: *\nDisallow: /\n');(out/'_headers').write_text('/*\n  X-Robots-Tag: noindex, nofollow\n  Referrer-Policy: no-referrer\n  Cache-Control: no-store\n')
archive=root/'downloads/DrillingWorkbench_Company_Web_Deploy.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for f in out.rglob('*'):
  if f.is_file():z.write(f,f.relative_to(out))
print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'containsAccessToken':False}))
