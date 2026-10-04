/* Browser-only photo preparation. HEIC decoder is loaded only when needed. */
(() => {
  'use strict';
  const decoderUrl = new URL('vendor/heic-to-1.6.5.js', document.currentScript.src).href;
  const MAX_INPUT = 40 * 1024 * 1024;
  const MAX_OUTPUT = 8 * 1024 * 1024;
  let decoderPromise;

  function loadDecoder() {
    if (!decoderPromise) {
      decoderPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = decoderUrl;
        script.onload = () => typeof window.HeicTo === 'function'
          ? resolve(window.HeicTo) : reject(new Error('HEIC decoder could not start.'));
        script.onerror = () => {
          script.remove();
          reject(new Error('Could not load HEIC support. Check your connection and try again.'));
        };
        document.head.append(script);
      }).catch(error => {
        decoderPromise = undefined;
        throw error;
      });
    }
    return decoderPromise;
  }

  async function isHeic(file) {
    if (/\.(heic|heif)$/i.test(file.name || '') || /^image\/hei[cf](?:-sequence)?$/i.test(file.type)) return true;
    const bytes = new Uint8Array(await file.slice(0, 64).arrayBuffer());
    const header = String.fromCharCode(...bytes);
    return header.slice(4, 8) === 'ftyp' && /heic|heix|hevc|hevx|mif1|msf1/.test(header.slice(8));
  }

  function nativeImage(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error('This photo could not be decoded.'));
      };
      img.src = url;
    });
  }

  async function prepare(file) {
    if (!(file instanceof Blob) || !file.size) throw new Error('Choose a non-empty photo.');
    if (file.size > MAX_INPUT) throw new Error('Choose a photo smaller than 40 MB.');
    const heic = await isHeic(file);
    if (!heic && !/^image\/(jpeg|png|webp|gif|avif|bmp)$/i.test(file.type) &&
        !/\.(jpe?g|png|webp|gif|avif|bmp)$/i.test(file.name || '')) {
      throw new Error('Choose a JPEG, PNG, WebP, HEIC, or HEIF photo.');
    }
    let decoded;
    try {
      decoded = await nativeImage(file);
    } catch (error) {
      if (!heic) throw new Error('Could not read this photo. Try another image.');
      const convert = await loadDecoder();
      try {
        // A bitmap avoids a lossy intermediate JPEG; libheif applies HEIF orientation.
        decoded = await convert({ blob: file, type: 'bitmap' });
      } catch (error) {
        throw new Error('Could not convert this HEIC photo. Try another photo or export it as JPEG.');
      }
    }
    const canvas = document.createElement('canvas');
    try {
      const width = decoded.naturalWidth || decoded.width;
      const height = decoded.naturalHeight || decoded.height;
      if (!width || !height) throw new Error('This photo has invalid dimensions.');
      const scale = Math.min(1, 2000 / Math.max(width, height));
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('This browser cannot prepare photos.');
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(decoded, 0, 0, canvas.width, canvas.height);
      const jpeg = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9));
      if (!jpeg || jpeg.type !== 'image/jpeg') throw new Error('Could not create a JPEG from this photo.');
      if (jpeg.size > MAX_OUTPUT) throw new Error('The prepared photo is too large. Choose a smaller photo.');
      return jpeg;
    } finally {
      if (typeof decoded.close === 'function') decoded.close();
      canvas.width = canvas.height = 1;
    }
  }
  window.PlatePhotos = Object.freeze({ prepare });
})();
