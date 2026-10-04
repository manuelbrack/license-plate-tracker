"""Browser integration checks. Requires Chrome remote debugging on 127.0.0.1:9223.
Uses only fake credentials and mocked GitHub writes.
"""
import base64,hashlib,json,os,socket,struct,urllib.request,subprocess,tempfile,pathlib,time
class CDP:
 def __init__(self,url):
  from urllib.parse import urlsplit
  u=urlsplit(url);self.s=socket.create_connection((u.hostname,u.port));self.i=0
  key=base64.b64encode(os.urandom(16)).decode();self.s.sendall(f'GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
  b=b''
  while not b.endswith(b'\r\n\r\n'):b+=self.s.recv(1)
  assert b'101' in b,b
 def read(self,n):
  b=b''
  while len(b)<n:b+=self.s.recv(n-len(b))
  return b
 def call(self,method,params={}):
  self.i+=1;raw=json.dumps({'id':self.i,'method':method,'params':params}).encode();mask=os.urandom(4);n=len(raw);header=bytes([129,128|n]) if n<126 else bytes([129,254])+struct.pack('!H',n)
  self.s.sendall(header+mask+bytes(x^mask[i%4] for i,x in enumerate(raw)))
  while True:
   a,b=self.read(2);n=b&127
   if n==126:n=struct.unpack('!H',self.read(2))[0]
   if n==127:n=struct.unpack('!Q',self.read(8))[0]
   result=json.loads(self.read(n))
   if result.get('id')==self.i:
    assert 'error' not in result,result
    return result.get('result',{})
 def js(self,expression):
  result=self.call('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
  assert 'exceptionDetails' not in result,result
  return result['result'].get('value')

from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import threading,functools
root=pathlib.Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(root),**kw)
 def log_message(self,*a):pass
 def do_GET(self):
  if self.path.startswith('/docs/photos/TX-'):
   self.path='/docs/photos/CA.jpg'
  super().do_GET()
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
base='http://127.0.0.1:'+str(server.server_port)
tab=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9223/json/new?about:blank',method='PUT')))
c=CDP(tab['webSocketDebuggerUrl'])
c.call('Page.enable')
def wait(expression):
 for _ in range(100):
  if c.js(expression):return
  time.sleep(.1)
 print(c.js("({errors:window.__errors,ready:document.readyState,text:document.body.innerText.slice(-1500)})")); raise AssertionError('Timed out: '+expression)
try:
 c.call('Page.navigate',{'url':base+'/tests/github-client.test.html'})
 wait('!!window.testResults')
 results=c.js('window.testResults');print('\n'.join(results));assert all(x.startswith('PASS') for x in results)
 mock=(root/'tests'/'ui-github-mock.js').read_text()
 c.call('Page.addScriptToEvaluateOnNewDocument',{'source':"window.__errors=[];addEventListener('error',e=>window.__errors.push(e.message));addEventListener('unhandledrejection',e=>window.__errors.push(String(e.reason)));"+mock})
 c.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1050,'deviceScaleFactor':1,'mobile':False})
 c.call('Page.navigate',{'url':base+'/docs/'})
 wait("document.querySelectorAll('.state-card').length===50 && !document.getElementById('unlock-editor').hidden")
 initial_count=len(json.loads((root/'docs/collection.json').read_text())['plates'])
 assert c.js("document.getElementById('count').textContent")==str(initial_count)
 c.js("document.getElementById('unlock-editor').click();document.getElementById('unlock-passphrase').value='incorrect';document.getElementById('unlock-form').requestSubmit()")
 wait("!document.getElementById('submit-unlock').disabled")
 assert c.js("!document.getElementById('unlock-error').hidden && document.getElementById('editor-controls').hidden")
 c.js("document.getElementById('unlock-passphrase').value='random test passphrase for tests only';document.getElementById('unlock-form').requestSubmit()")
 wait("!document.getElementById('editor-controls').hidden")
 assert c.js("document.getElementById('unlock-passphrase').value") == ''
 c.js("document.getElementById('add-find').click();document.getElementById('upload-state').value='TX'")
 c.js("""(async()=>{const blob=await(await fetch('photos/CA.jpg')).blob();const dt=new DataTransfer();dt.items.add(new File([blob],'photo.jpg',{type:'image/jpeg'}));document.getElementById('upload-file').files=dt.files;await document.getElementById('upload-file').onchange({target:document.getElementById('upload-file')});})()""")
 assert c.js("!document.getElementById('save-photo').disabled && !!document.querySelector('#upload-preview img')")
 c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 assert c.js('document.documentElement.scrollWidth<=innerWidth')
 c.js("document.getElementById('crop-zoom').value='6';document.getElementById('crop-zoom').dispatchEvent(new Event('input'));document.querySelector('#crop-editor button').click()")
 assert c.js("Number(document.getElementById('crop-zoom').value)")==1
 c.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1050,'deviceScaleFactor':1,'mobile':False})
 # Pick an off-center crop; drag and keyboard adjustment must stay bounded.
 c.js("document.getElementById('crop-zoom').value='3';document.getElementById('crop-zoom').dispatchEvent(new Event('input'));document.getElementById('crop-y').value='80';document.getElementById('crop-y').dispatchEvent(new Event('input'))")
 initial_crop=c.js("cropEditor.getCrop()")
 c.js("document.getElementById('upload-preview').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true}))")
 assert c.js("cropEditor.getCrop().x") < initial_crop['x']
 bounds=c.js("(()=>{const r=document.getElementById('upload-preview').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
 c.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':bounds['x'],'y':bounds['y'],'button':'left','clickCount':1})
 c.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':bounds['x']+35,'y':bounds['y']-20,'button':'left','buttons':1})
 c.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':bounds['x']+35,'y':bounds['y']-20,'button':'left','clickCount':1})
 chosen=c.js("cropEditor.getCrop()")
 assert chosen['x'] < initial_crop['x'] and chosen['y'] > initial_crop['y']
 assert c.js("(()=>{const c=cropEditor.getCrop(),i=document.querySelector('#upload-preview img');return Math.abs(c.width*i.naturalWidth/(c.height*i.naturalHeight)-1.83)<0.001})()")
 shot=c.call('Page.captureScreenshot',{'format':'png'});pathlib.Path('/private/tmp/joleen-crop-editor.png').write_bytes(base64.b64decode(shot['data']))
 c.js("document.getElementById('save-photo').onclick()")
 stored=c.js("JSON.parse(window.__mockWrites.find(x=>x.path==='/git/blobs'&&x.body.encoding==='utf-8').body.content).plates.TX.crop")
 assert stored==chosen
 c.js("openState('TX')")
 assert c.js("document.querySelector('#photo-stage img').style.width==='' && !document.querySelector('#photo-stage img').classList.contains('cropped-thumbnail')")
 c.js("document.getElementById('close-dialog').click()")
 assert c.js("window.__mockWrites.filter(x=>x.method==='PATCH').length") == 1
 assert c.js("document.getElementById('publish-banner').textContent.includes('Publishing')")
 assert c.js("document.getElementById('count').textContent") == str(initial_count+1)
 c.js("window.__mockPublished=true;watchPublication(JSON.parse(sessionStorage.getItem('joleen-pending-publication-v1')))")
 wait("document.getElementById('publish-banner').textContent.startsWith('Published')")
 assert c.js("sessionStorage.getItem('joleen-pending-publication-v1')") is None
 assert c.js("(()=>{const card=[...document.querySelectorAll('.state-card')].find(c=>c.getAttribute('aria-label').startsWith('Texas,'));return card.querySelector('img').classList.contains('cropped-thumbnail')})()")
 c.js("document.getElementById('map-toggle').click()")
 assert c.js("document.querySelectorAll('.map-state.collected').length") == initial_count+1
 c.js("document.getElementById('lock-editor').click()")
 assert c.js("document.getElementById('editor-controls').hidden")
 assert c.js("!JSON.stringify(localStorage).includes('fake') && !JSON.stringify(sessionStorage).includes('fake')")
 c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 assert c.js('document.documentElement.scrollWidth<=innerWidth')
 print('PASS crop: keyboard and pointer positioning, aspect ratio, saved rectangle, grid-only framing, full photo detail.')
 print('PASS UI: wrong/correct passphrase, upload preparation, one atomic commit, pending/published banner, updated map, lock, no stored token, mobile width.')
finally:
 urllib.request.urlopen('http://127.0.0.1:9223/json/close/'+tab['id']).read()
 server.shutdown();server.server_close()
