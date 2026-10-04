// Test-only transport. Never forwards any GitHub request or uses real credentials.
(() => {
  const nativeFetch=window.fetch.bind(window);
  window.__mockWrites=[]; window.__mockPublished=false;
  let initial, next, encrypted;
  const ok=value=>new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
  window.fetch=async (url,options={})=>{
    const parsed=new URL(url,location.href),path=parsed.pathname;
    if(path.endsWith('/upload-config.json')){
      encrypted ||= await PlateGitHub.encryptToken('fake-test-token','random test passphrase for tests only');return ok(encrypted);
    }
    if(path.endsWith('/collection.json')&&parsed.origin===location.origin){
      initial ||= await (await nativeFetch(url,options)).json();
      return ok(window.__mockPublished&&next?next:initial);
    }
    if(parsed.origin==='https://api.github.com'){
      const p=path.replace('/repos/manuelbrack/license-plate-tracker','');
      const method=options.method||'GET',body=options.body?JSON.parse(options.body):null;
      if(method!=='GET')window.__mockWrites.push({path:p,method,body});
      if(p==='')return ok({permissions:{push:true}});
      if(p.startsWith('/git/ref/heads/'))return ok({object:{sha:'old-head'}});
      if(p==='/git/commits/old-head')return ok({tree:{sha:'old-tree'}});
      if(p==='/contents/docs/collection.json')return ok({content:btoa(JSON.stringify(initial))});
      if(p==='/git/blobs'){
        if(body.encoding==='utf-8')next=JSON.parse(body.content);
        return ok({sha:body.encoding==='utf-8'?'manifest-blob':'photo-blob'});
      }
      if(p==='/git/trees')return ok({sha:'new-tree'});
      if(p==='/git/commits')return ok({sha:'mock-upload-commit'});
      if(p.startsWith('/git/refs/heads/')){
        if(body.force!==false)throw new Error('Force push forbidden');return ok({object:{sha:body.sha}});
      }
      if(p==='/pages/builds/latest')return ok({commit:'mock-upload-commit',status:'building'});
      throw new Error('Unexpected GitHub request in test: '+p);
    }
    return nativeFetch(url,options);
  };
})();
