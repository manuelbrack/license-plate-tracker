(function (global) {
  'use strict';
  const OWNER = 'manuelbrack';
  const REPO = 'license-plate-tracker';
  const BRANCH = 'feat/plate-tracker';
  const API = `https://api.github.com/repos/${OWNER}/${REPO}`;
  const STATES = new Set('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split(' '));
  const ITERATIONS = 600000;
  const encoder = new TextEncoder();
  function failure(code, message, status) {
    const error = new Error(message);
    error.code = code;
    if (status) error.status = status;
    return error;
  }
  function base64(bytes) {
    let value = '';
    for (let i = 0; i < bytes.length; i += 8192) value += String.fromCharCode(...bytes.subarray(i, i + 8192));
    return btoa(value);
  }
  function unbase64(value, max) {
    if (typeof value !== 'string' || value.length > max || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) throw failure('credential', 'Invalid encrypted credential.');
    return Uint8Array.from(atob(value), c => c.charCodeAt(0));
  }
  async function key(passphrase, salt, usage) {
    if (typeof passphrase !== 'string' || !passphrase || passphrase.length > 4096) throw failure('credential', 'Enter a valid passphrase.');
    const material = await crypto.subtle.importKey('raw', encoder.encode(passphrase), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey({name: 'PBKDF2', salt, iterations: ITERATIONS, hash: 'SHA-256'}, material, {name: 'AES-GCM', length: 256}, false, [usage]);
  }
  async function encryptToken(token, passphrase) {
    if (typeof token !== 'string' || !token.trim() || token.length > 4096) throw failure('credential', 'Enter a valid GitHub token.');
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await crypto.subtle.encrypt({name: 'AES-GCM', iv}, await key(passphrase, salt, 'encrypt'), encoder.encode(token.trim()));
    return {version: 1, kdf: 'PBKDF2-SHA256', iterations: ITERATIONS, salt: base64(salt), iv: base64(iv), ciphertext: base64(new Uint8Array(ciphertext))};
  }
  async function decryptToken(envelope, passphrase) {
    if (!envelope || envelope.version !== 1 || envelope.kdf !== 'PBKDF2-SHA256' || envelope.iterations !== ITERATIONS) throw failure('credential', 'Unsupported encrypted credential.');
    const salt = unbase64(envelope.salt, 24), iv = unbase64(envelope.iv, 16), ciphertext = unbase64(envelope.ciphertext, 22000);
    if (salt.length !== 16 || iv.length !== 12 || ciphertext.length < 17 || ciphertext.length > 16400) throw failure('credential', 'Invalid encrypted credential.');
    try {
      const clear = await crypto.subtle.decrypt({name: 'AES-GCM', iv}, await key(passphrase, salt, 'decrypt'), ciphertext);
      const token = new TextDecoder('utf-8', {fatal: true}).decode(clear);
      if (!token.trim() || token.length > 4096) throw new Error();
      return token;
    } catch (_) { throw failure('unlock', 'Could not unlock. Check the passphrase and try again.'); }
  }
  function validateCrop(crop) {
    const fields = ['x', 'y', 'width', 'height'];
    if (!crop || typeof crop !== 'object' || Array.isArray(crop) || Object.keys(crop).length !== fields.length || !fields.every(field => Object.prototype.hasOwnProperty.call(crop, field) && Number.isFinite(crop[field]))) throw failure('crop', 'Choose a valid overview crop.');
    const {x, y, width, height} = crop;
    if (x < 0 || y < 0 || x >= 1 || y >= 1 || width <= 0 || height <= 0 || width > 1 || height > 1 || x + width > 1 + 1e-6 || y + height > 1 + 1e-6) throw failure('crop', 'The overview crop must stay inside the photo.');
    return {x, y, width: Math.min(width, 1 - x), height: Math.min(height, 1 - y)};
  }
  function validateManifest(manifest) {
    if (!manifest || manifest.version !== 1 || typeof manifest.revision !== 'string' || manifest.revision.length > 128 || !manifest.plates || typeof manifest.plates !== 'object' || Array.isArray(manifest.plates)) throw failure('manifest', 'The collection manifest is invalid.');
    for (const [state, entry] of Object.entries(manifest.plates)) {
      if (!STATES.has(state) || !entry || typeof entry !== 'object' || Array.isArray(entry) || typeof entry.url !== 'string' || !/^photos\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}\.(?:jpg|jpeg|png|webp)$/i.test(entry.url)) throw failure('manifest', 'The collection contains an invalid photo path or state.');
      if (Object.prototype.hasOwnProperty.call(entry, 'crop')) {
        try { validateCrop(entry.crop); }
        catch (_) { throw failure('manifest', 'The collection contains an invalid overview crop.'); }
      }
    }
    return manifest;
  }
  function canonical(value) {
    if (value === null || typeof value !== 'object') return JSON.stringify(value);
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
  }
  function createClient(token) {
    if (typeof token !== 'string' || !token.trim() || /\s/.test(token)) throw failure('credential', 'Invalid GitHub token.');
    async function request(path, method = 'GET', body) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 25000);
      try {
        const response = await fetch(API + path, {
          method, cache: 'no-store', redirect: 'error', signal: controller.signal,
          headers: {Accept: 'application/vnd.github+json', Authorization: `Bearer ${token}`, 'X-GitHub-Api-Version': '2022-11-28', ...(body ? {'Content-Type': 'application/json'} : {})},
          ...(body ? {body: JSON.stringify(body)} : {})
        });
        if (!response.ok) {
          const status = response.status;
          if (status === 429 || (status === 403 && (response.headers.get('x-ratelimit-remaining') === '0' || response.headers.get('retry-after')))) throw failure('rate-limit', 'GitHub is limiting requests. Wait a few minutes and try again.', status);
          if (status === 401) throw failure('authentication', 'The upload token has expired or was revoked. Ask the owner to renew it.', status);
          if (status === 403 || status === 404) throw failure('permissions', 'GitHub access was denied. Check token access and Contents write permission.', status);
          if (status === 409 || status === 422) throw failure('conflict', 'The collection changed during upload. Refresh and try again.', status);
          if (method === 'PATCH' && status >= 500) throw failure('uncertain', 'GitHub could not confirm the save. Refresh the collection to check whether the photo saved before uploading again.', status);
          throw failure('github', 'GitHub could not complete the request. Please try again later.', status);
        }
        return await response.json();
      } catch (error) {
        if (typeof error.code === 'string') throw error;
        if (method === 'PATCH') throw failure('uncertain', 'Connection interrupted while saving. Refresh the collection to check whether the photo saved before uploading again.');
        throw failure('network', 'Could not reach GitHub. Check your connection and try again.');
      } finally { clearTimeout(timer); }
    }
    async function validate() {
      const repo = await request('');
      if (repo.permissions && !repo.permissions.push) throw failure('permissions', 'This token cannot update the collection.');
      await request('/git/ref/heads/' + BRANCH);
      return true;
    }
    async function readCollection() {
      const ref = await request('/git/ref/heads/' + BRANCH);
      const head = ref.object.sha;
      const commit = await request('/git/commits/' + head);
      const file = await request('/contents/docs/collection.json?ref=' + encodeURIComponent(head));
      let manifest;
      try { manifest = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(unbase64(file.content.replace(/\s/g, ''), 2000000))); }
      catch (_) { throw failure('manifest', 'The collection manifest could not be read.'); }
      return {head, tree: commit.tree.sha, manifest: validateManifest(manifest)};
    }
    async function uploadPhoto({state, blob, expectedEntry, crop}) {
      if (!STATES.has(state) || !(blob instanceof Blob) || blob.type !== 'image/jpeg' || !blob.size || blob.size > 8 * 1024 * 1024 || expectedEntry === undefined) throw failure('photo', 'Choose a valid state and a JPEG photo smaller than 8 MB.');
      const overviewCrop = crop === undefined ? undefined : validateCrop(crop);
      const url = 'photos/' + state + '-' + crypto.randomUUID() + '.jpg';
      let photoSha;
      for (let attempt = 0; attempt < 3; attempt++) {
        const latest = await readCollection();
        if (canonical(latest.manifest.plates[state] || null) !== canonical(expectedEntry)) throw failure('state-conflict', 'Someone updated this state. Refresh and review its photo before replacing it.');
        if (!photoSha) photoSha = (await request('/git/blobs', 'POST', {content: base64(new Uint8Array(await blob.arrayBuffer())), encoding: 'base64'})).sha;
        const entry = overviewCrop === undefined ? {url} : {url, crop: overviewCrop};
        const manifest = {...latest.manifest, revision: crypto.randomUUID(), plates: {...latest.manifest.plates, [state]: entry}};
        const manifestSha = (await request('/git/blobs', 'POST', {content: JSON.stringify(manifest, null, 2) + '\n', encoding: 'utf-8'})).sha;
        const tree = await request('/git/trees', 'POST', {base_tree: latest.tree, tree: [
          {path: 'docs/' + url, mode: '100644', type: 'blob', sha: photoSha},
          {path: 'docs/collection.json', mode: '100644', type: 'blob', sha: manifestSha}
        ]});
        const commit = await request('/git/commits', 'POST', {message: `Add ${state} photo to Joleen's collection`, tree: tree.sha, parents: [latest.head]});
        try {
          await request('/git/refs/heads/' + BRANCH, 'PATCH', {sha: commit.sha, force: false});
          return {commit: commit.sha, manifest};
        } catch (error) {
          if (error.code !== 'conflict' || attempt === 2) throw error;
        }
      }
    }
    return Object.freeze({validate, readCollection, uploadPhoto});
  }
  global.PlateGitHub = Object.freeze({encryptToken, decryptToken, validateCrop, validateManifest, createClient});
})(window);
