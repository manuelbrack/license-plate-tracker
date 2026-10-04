# License plate tracker

- Scope: local webpage with alphabetized 50-state photo grid and geographic map. No deployment or external account.
- Design: midnight navy, electric lime collected states, subdued gray missing states, editorial typography and plate-shaped tiles.
- Persistence: Python standard-library server saves uploads in ignored `data/`; no browser-only source of truth or runtime dependencies.
- Map: bundled us-atlas Albers-projected topology, including Alaska and Hawaii. Exclude DC and territories.
- Implementation: main agent owns frontend; backend agent owns Python server and API integration tests.
- Verification: API integration tests plus frontend/map structural checks; browser QA subject to available tooling.
- Completed: both views, progress count, upload resizing, photo modal, replacement/deletion, keyboard activation, small-state map buttons, responsive layouts and error states.
- Verification completed: four HTTP integration tests passed; verified all 50 alphabetical state entries map to geographic geometry. Headless Chrome checks passed for 50 grid cards and map paths, keyboard opening, actual frontend upload, progress/highlight updates, reload persistence, deletion, and 390px mobile width. Desktop grid/map and mobile screenshots inspected. Browser tests used an isolated temporary collection; real collection remains empty.
- Handoff: `python3 server.py` serves http://127.0.0.1:5173. README documents startup, local-only storage, photo formats, backup, tests, and map attribution. No publication or external synchronization performed.
- Personalized the heading, browser title, collection accessibility label, header and metadata for Joleen. Checked the HTML edits and whitespace; no behavior changed.
