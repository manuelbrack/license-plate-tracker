HEIC photo decoding
===================

heic-to 1.6.5 by hoppergee and contributors
https://github.com/hoppergee/heic-to
License: GNU LGPL version 3 or later (heic-to-LICENSE.txt and GPL-3.0.txt).
The unmodified browser IIFE is vendored as heic-to-1.6.5.js and loaded only
when native photo decoding fails for HEIC/HEIF. No CDN is contacted at runtime.

Distribution and source, pinned version:
https://registry.npmjs.org/heic-to/-/heic-to-1.6.5.tgz
https://github.com/hoppergee/heic-to/tree/v1.6.5
The npm archive includes wrapper source, build scripts, and generated libheif.

Bundled decoder: libheif 1.23.5, struktur AG, Dirk Farin, and contributors.
https://github.com/strukturag/libheif/tree/v1.23.5
HEVC codec: libde265 1.0.16, struktur AG and contributors.
https://github.com/strukturag/libde265/tree/v1.0.16
Both decoder libraries are GNU LGPL version 3 or later. Their sources and
build instructions are available at the links above and in heic-to's README.

This website loads the decoder as a separate, replaceable script. You may
replace it with an interface-compatible modified build; application code
does not prohibit modification or reverse engineering for that purpose.

SHA-256 of the unmodified vendored browser script:
c94d3bce5d9886be1989c270e53c98585ba67af1863fc156b4c72a27c4a18bc1
