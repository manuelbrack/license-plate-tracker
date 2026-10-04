# Joleen’s Collection — State by State

**Live site: https://manuelbrack.github.io/license-plate-tracker/**

A fifty-state license plate collection with an alphabetical photo grid and an interactive geographic map. The public page is view-only by default. Passphrase-unlocked editing adds or replaces photos through GitHub, including HEIC/HEIF images. Uploads publish to the public collection after GitHub Pages rebuilds.

## Enable browser uploads

The implementation is ready, but requires a **new dedicated fine-grained GitHub token**. Do not use the general-purpose token from `gh`, paste credentials into chat, or commit plaintext credentials.

```sh
cd /Users/mbrack/Public/Projects/license-plate-tracker
python3 setup_upload.py
```

Open **http://127.0.0.1:5175** and follow its instructions:

1. Create a fine-grained token for owner `manuelbrack`, with **Only select repositories → license-plate-tracker**, **Contents: Read and write**, an expiration date, and no other optional permissions.
2. Enter the token into the local setup page and generate a strong passphrase (or use at least six independently random words). Save the passphrase for Joleen.
3. Click **Encrypt & enable uploads**. Encryption happens in the browser; only ciphertext reaches the local server. The helper commits and pushes `docs/upload-config.json`, then GitHub Pages publishes it.
4. Refresh the live site. **Unlock editing** appears after the encrypted configuration is deployed. Enter the passphrase, choose a state and photo, then **Publish photo**.

The helper requires a clean checkout of `feat/plate-tracker` and working `personal` GitHub remote. It fetches and fast-forwards before publishing. If another upload races the config push, reconcile the branch and retry; it never force pushes. Stop the helper with Control-C when finished.

The setup page validates access without making a test commit. GitHub enforces actual write permissions when publishing a photo. An expired or revoked token requires repeating setup with a new token. **When rotating a passphrase, revoke and replace the old token too**: previous encrypted bundles remain in Git history.

## Security and upload behavior

- Dedicated token encrypted using AES-256-GCM, a random 16-byte salt and 12-byte IV, and PBKDF2-HMAC-SHA256 with 600,000 iterations.
- Encrypted bundle is public. Passphrases can be attacked offline; there is no meaningful browser-side guessing limit.
- Decrypted token is memory-only, sent solely to the fixed GitHub API repository endpoint, and never stored in local/session storage or logs. Editing locks after 15 minutes of inactivity or page reload.
- A Contents-write token can modify repository code, not only photos. This is a trusted-editor arrangement, not server-enforced upload-only access.
- HEIC/HEIF decoding occurs locally: native browser decoder first, bundled `heic-to` fallback. Input limit 40 MB; output JPEG longest edge 2,000 pixels, at most 8 MB. Re-encoding removes source metadata. Keep original photos separately.
- Each upload creates one commit containing both the image and collection manifest. Non-forced branch updates preserve concurrent changes to other states; same-state conflicts require review.
- Publishing status checks the actual deployed manifest and photo. A nonsecret pending commit marker survives reload within the current tab. API limits or deployment delays do not discard the saved photo.
- Public visits check build status anonymously. No GitHub token is needed for viewing.

## Source of truth and publishing updates

**`docs/collection.json` and its referenced `docs/photos/` are the authoritative public collection.** Browser uploads update these directly on `feat/plate-tracker`, the GitHub Pages source branch. The page loads the manifest at runtime; no build-time photo embedding is necessary.

Before editing the site locally, pull browser changes. Then regenerate the interface:

```sh
git switch feat/plate-tracker
git pull --ff-only personal feat/plate-tracker
python3 export_static.py
python3 -m unittest -v test_export_static test_setup_upload test_server
git add docs site export_static.py
git commit -m 'Update collection interface'
git push personal feat/plate-tracker
```

The exporter bootstraps from local `data/` only when there is no public manifest yet. Thereafter it preserves the published manifest, photos, and encrypted configuration. Local tracker uploads are separate and do not replace the public collection. For public updates, use the website’s unlocked uploader.

The app is static HTML/CSS/JS, with no runtime server or external CDN dependencies. Serve `docs/` over HTTP(S); opening the HTML as a `file://` URL is no longer supported because it reads a JSON manifest. The HEIC decoder downloads only when needed.

## Local-only tracker

```sh
python3 server.py
```

Open **http://127.0.0.1:5173**. The original local tracker retains its upload/delete functionality and stores photos under ignored `data/`. Back up that folder separately. It does not sync changes from the public collection. No Python dependencies required (Python 3.9+).

## Verification

```sh
python3 -m unittest -v test_server test_export_static test_setup_upload
```

`tests/github-client.test.html` runs browser crypto/API tests with fake tokens and mocked GitHub requests. With a separate Chrome debugging session on port 9223, `python3 tests/run_browser_checks.py` runs those tests plus the upload/unlock/publishing UI flow. No test makes real GitHub writes.

## Third-party assets

US map: [us-atlas 3](https://github.com/topojson/us-atlas), ISC license, derived from US Census Bureau boundaries. See `MAP-LICENSE.txt`.

HEIC decoder: vendored `heic-to` 1.6.5 and libheif, LGPL-3.0-or-later. See `site/vendor/README.txt` and accompanying licenses, also distributed with the published site.

Uploads include a grid preview editor: drag to reposition, zoom, use horizontal/vertical sliders, or adjust with arrow keys. Crop metadata is saved alongside the full photo; only overview thumbnails use it. Opening a state always shows the full image. HEIC conversion happens before choosing the preview crop.
