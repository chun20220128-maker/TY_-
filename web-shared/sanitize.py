"""Create a data-free deployment: no real reference prices or filled template cells."""
import re,base64,io,zipfile
from xml.dom import minidom
HEADERS=('工程名稱','工程編號','計畫編號','專案編號','鑽探委外廠商','委外廠商')
def template(raw):
 source=zipfile.ZipFile(io.BytesIO(base64.b64decode(raw)));output=io.BytesIO()
 with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as target:
  for item in source.infolist():
   data=source.read(item.filename)
   if item.filename.endswith('.xml'):
    try:
     doc=minidom.parseString(data)
     if item.filename.startswith('xl/worksheets/'):
      for cell in doc.getElementsByTagNameNS('*','c'):
       for formula in list(cell.getElementsByTagNameNS('*','f')):formula.parentNode.removeChild(formula)
       if cell.getAttribute('t') not in ['s','inlineStr']:
        for value in cell.getElementsByTagNameNS('*','v'):
         for child in list(value.childNodes):value.removeChild(child)
         value.appendChild(doc.createTextNode('0'))
     for tag in ['creator','lastModifiedBy','Company','title','subject','description','keywords']:
      if item.filename.startswith('docProps/'):
       for element in doc.getElementsByTagNameNS('*',tag):
        for child in list(element.childNodes):element.removeChild(child)
     for element in doc.getElementsByTagNameNS('*','t'):
      text=''.join(n.data for n in element.childNodes if n.nodeType==n.TEXT_NODE)
      if any(text.strip().startswith(h) for h in HEADERS):
       label=next(h for h in HEADERS if text.strip().startswith(h));replacement=label+'：'
      elif '有限公司' in text or re.fullmatch(r'[\d,.+\-()%/\s]+',text) or re.fullmatch(r'BH[-－]?\d+',text,re.I):replacement=''
      else:continue
      for child in list(element.childNodes):element.removeChild(child)
      element.appendChild(doc.createTextNode(replacement))
     if item.filename.startswith('word/'):
      for paragraph in doc.getElementsByTagNameNS('*','p'):
       runs=list(paragraph.getElementsByTagNameNS('*','t'));text=''.join(''.join(n.data for n in run.childNodes if n.nodeType==n.TEXT_NODE) for run in runs)
       if runs and any(text.strip().startswith(h) for h in HEADERS):
        label=next(h for h in HEADERS if text.strip().startswith(h))+'：'
        for index,run in enumerate(runs):
         for child in list(run.childNodes):run.removeChild(child)
         run.appendChild(doc.createTextNode(label if index==0 else ''))
     data=doc.toxml(encoding='utf-8')
    except Exception as exc:raise ValueError('Cannot sanitize template XML '+item.filename) from exc
   target.writestr(item,data)
 return base64.b64encode(output.getvalue()).decode()
def application(text,private_strings=()):
 for value in private_strings:
  if value:text=text.replace(value,'')
 text,count=re.subn(r'(<script[^>]*id="bundledHistory"[^>]*>).*?(</script>)',r'\1[]\2',text,flags=re.S)
 if count!=1:raise ValueError('Historical data block not found')
 text=re.sub(r'(const defs=)([^\n]+)',lambda m:m[1]+re.sub(r',\s*\d+(?:\.\d+)?\]',',0]',m[2]),text)
 for name in ['BLANK_TEMPLATE','REQUIREMENT_TEMPLATE','ESTIMATE_TEMPLATE']:
  pattern=r'(const '+name+r'=)"([A-Za-z0-9+/=]+)";'
  text,count=re.subn(pattern,lambda m:m[1]+'"'+template(m[2])+'";',text)
  if count!=1:raise ValueError('Template not found '+name)
 return text
