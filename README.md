# Joleen’s Collection — State by State

A local license plate photo tracker, built with plain HTML/CSS/JavaScript and a Python standard-library server. No package installation or accounts required.

The read-only collection is published at **https://manuelbrack.github.io/license-plate-tracker/**. The public version includes the grid, map, and photo viewer, with no upload or removal controls.

## Run

```sh
cd /Users/mbrack/Public/Projects/license-plate-tracker
python3 server.py
```

Open **http://127.0.0.1:5173**. Requires Python 3.9+ and a modern browser. Keep the server running while using the app; press Control-C to stop it. If the port is occupied, use `python3 server.py --port 5174` and open that port instead.

## Use

- Toggle between the alphabetical 50-state grid and the geographic map.
- Select a state to upload a photo. Collected states show the photo in the grid and turn lime on the map.
- Select a collected state to view, replace, or remove its photo.
- Small northeastern states have additional named buttons below the map for easier selection.

The collection starts empty. JPG, PNG, and WebP photos work; export HEIC photos to JPG if your browser cannot decode them. Uploads are resized to a maximum of 2,000 pixels on the longest edge and saved as JPEG. Keep original photos separately.

The local collection has been seeded with Joleen’s photos, including Washington: 13 states (26%). A fresh checkout does not include private `data/`; the published snapshot is in `docs/`.

## Refresh the static site

After updating the local collection, run:

```sh
python3 export_static.py
python3 -m unittest -v test_export_static
git add docs
git commit -m 'Update Joleen’s published collection'
git push personal feat/plate-tracker
```

GitHub Pages publishes the `docs/` folder on `feat/plate-tracker`. Exporting copies the current collection into that folder; only commit and push photos intended for the public site. Uploads in the local tracker do not change the published snapshot until it is exported and pushed again.

## Storage

Photos and collection metadata are saved in `data/` within this project, excluded from Git. Back up that entire folder to preserve the collection. Nothing is uploaded to an external service. The server listens on this computer only; the app does not sync between devices or provide a publicly hosted URL.

## Checks

```sh
python3 -m unittest -v test_server
```

Integration tests cover uploading, replacing, restarting with saved data, deleting, invalid inputs, local-origin protection, and private-path protection. Tests use temporary data, separate from the real collection.

## Map attribution

The bundled `dist/states-topology.json` is [us-atlas 3](https://github.com/topojson/us-atlas), `states-albers-10m.json`, distributed under the ISC license. It derives from US Census Bureau cartographic boundaries. Alaska and Hawaii appear as insets. DC and territories are excluded from this fifty-state tracker. See `MAP-LICENSE.txt`.
