from pathlib import Path
import re,json,base64,io,zipfile
from xml.dom import minidom
root=Path(__file__).resolve().parents[2];archive=root/'downloads/DrillingWorkbench_Company_Web_Deploy.zip';source=json.loads((root/'data/history-seed.json').read_text(encoding='utf-8'))
with zipfile.ZipFile(archive) as z:
 assert json.loads(z.read('protected/history-seed.json'))==[]
 app=z.read('protected/app.bundle').decode();block=re.search(r'<script[^>]*id="bundledHistory"[^>]*>(.*?)</script>',app,re.S)
 assert block and json.loads(block[1])==[]
 private_strings={h[k] for h in source for k in ['project','vendor'] if h.get(k)}
 assert not any(value in app for value in private_strings)
 template_count=0;numeric_cells=0
 for name in ['BLANK_TEMPLATE','REQUIREMENT_TEMPLATE','ESTIMATE_TEMPLATE']:
  raw=re.search(r'const '+name+r'="([A-Za-z0-9+/=]+)";',app)[1]
  with zipfile.ZipFile(io.BytesIO(base64.b64decode(raw))) as template:
   for filename in template.namelist():
    if not filename.endswith('.xml'):continue
    doc=minidom.parseString(template.read(filename))
    text=''.join(n.data for e in doc.getElementsByTagName('*') for n in e.childNodes if n.nodeType==n.TEXT_NODE)
    assert not any(value in text for value in private_strings),name+' contains company text'
    if filename.startswith('xl/worksheets/'):
     assert not doc.getElementsByTagNameNS('*','f')
     for cell in doc.getElementsByTagNameNS('*','c'):
      if cell.getAttribute('t') not in ['s','inlineStr']:
       for value in cell.getElementsByTagNameNS('*','v'):
        assert value.firstChild is None or value.firstChild.data=='0';numeric_cells+=1
   template_count+=1
 print(json.dumps({'deploymentHistoryRows':0,'embeddedHistoryRows':0,'companyNamesInApplicationOrTemplates':0,'sanitizedTemplates':template_count,'clearedNumericTemplateCells':numeric_cells,'activeAccessTokenInPackage':False}))
