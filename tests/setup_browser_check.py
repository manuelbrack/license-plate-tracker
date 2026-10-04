"""Exercise local credential setup in Chrome with fake GitHub and a mock publisher."""
import base64
from http.server import HTTPServer
import json
from pathlib import Path
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import setup_upload

# Reuse the dependency-free Chrome protocol helper without executing its tests.
helpers = {}
exec((ROOT / "tests/run_browser_checks.py").read_text().split("from http.server")[0], helpers)
CDP = helpers["CDP"]
received = []


def mock_publish(root, envelope):
    received.append(envelope)
    return "Encrypted credential published. GitHub Pages will update shortly. Keep the passphrase somewhere safe."


server = HTTPServer(("127.0.0.1", 0), setup_upload.make_handler(ROOT, mock_publish))
threading.Thread(target=server.serve_forever, daemon=True).start()
tab = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:9223/json/new?about:blank", method="PUT")))
chrome = CDP(tab["webSocketDebuggerUrl"])


def wait(expression):
    for _ in range(100):
        if chrome.js(expression):
            return
        time.sleep(.1)
    raise AssertionError("Browser condition timed out")


try:
    chrome.call("Page.enable")
    chrome.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
      window.__errors=[];
      window.__githubRequests=[];
      window.__postedConfig=null;
      addEventListener('error',event=>window.__errors.push(event.message));
      addEventListener('unhandledrejection',event=>window.__errors.push(String(event.reason)));
      const nativeFetch=window.fetch;
      window.fetch=async (url,options={})=>{
        const absolute=new URL(url,location.href);
        if(absolute.origin==='https://api.github.com'){
          window.__githubRequests.push({path:absolute.pathname,method:options.method});
          if(options.method!=='GET')throw Error('GitHub mutation forbidden in setup test');
          const payload=absolute.pathname==='/repos/manuelbrack/license-plate-tracker'
            ? {permissions:{push:true}}
            : absolute.pathname==='/repos/manuelbrack/license-plate-tracker/git/ref/heads/feat/plate-tracker'
            ? {object:{sha:'fake-head'}} : null;
          if(!payload)throw Error('Unexpected GitHub request');
          return new Response(JSON.stringify(payload),{status:200,headers:{'Content-Type':'application/json'}});
        }
        if(absolute.origin!==location.origin)throw Error('External request forbidden in setup test');
        if(absolute.pathname==='/config')window.__postedConfig=options.body;
        return nativeFetch(url,options);
      };
    """})
    chrome.call("Emulation.setDeviceMetricsOverride", {"width": 1100, "height": 1400, "deviceScaleFactor": 1, "mobile": False})
    chrome.call("Page.navigate", {"url": f"http://127.0.0.1:{server.server_port}/"})
    wait("!!document.querySelector('#setup-form') && !!window.PlateGitHub")
    chrome.js("document.querySelector('#generate').click()")
    assert chrome.js("document.querySelector('#passphrase').value.length===32 && document.querySelector('#passphrase').value===document.querySelector('#confirm').value")
    assert chrome.js("document.querySelector('#passphrase').type==='password'")
    chrome.js("document.querySelector('#show').click()")
    assert chrome.js("document.querySelector('#passphrase').type==='text' && document.querySelector('#confirm').type==='text'")
    chrome.js("document.querySelector('#show').click()")
    chrome.js("document.querySelector('#token').value='github_pat_fake_setup_test_only';document.querySelector('#setup-form').requestSubmit()")
    wait("document.querySelector('#submit').textContent==='Uploads enabled'")
    assert len(received) == 1
    setup_upload.validate_envelope(received[0])
    assert chrome.js("window.__githubRequests.length===2 && window.__githubRequests.every(request=>request.method==='GET')")
    assert chrome.js("!window.__postedConfig.includes('github_pat_fake_setup_test_only') && !window.__postedConfig.includes(document.querySelector('#passphrase').value)")
    assert chrome.js("(async()=>await PlateGitHub.decryptToken(JSON.parse(window.__postedConfig),document.querySelector('#passphrase').value)==='github_pat_fake_setup_test_only')()")
    assert chrome.js("document.querySelector('#token').value==='' && !JSON.stringify(localStorage).includes('github_pat_') && !JSON.stringify(sessionStorage).includes('github_pat_')")
    assert chrome.js("window.__errors.length===0")
    screenshot = "/private/tmp/joleen-token-setup-browser.png"
    Path(screenshot).write_bytes(base64.b64decode(chrome.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})["data"]))
    chrome.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
    assert chrome.js("document.documentElement.scrollWidth<=innerWidth")
    print("PASS setup wizard: generated passphrase, visibility toggle, read-only GitHub validation, browser encryption, ciphertext-only POST, successful unlock, cleared token, no storage, no browser errors, mobile width.")
    print("Screenshot: " + screenshot)
finally:
    urllib.request.urlopen("http://127.0.0.1:9223/json/close/" + tab["id"]).read()
    server.shutdown()
    server.server_close()
