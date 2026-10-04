(function () {
  'use strict';
  const form = document.querySelector('#setup-form');
  const tokenInput = document.querySelector('#token');
  const passphraseInput = document.querySelector('#passphrase');
  const confirmation = document.querySelector('#confirm');
  const status = document.querySelector('#status');
  const submit = document.querySelector('#submit');
  const generate = document.querySelector('#generate');
  document.querySelector('#show').addEventListener('change', event => {
    passphraseInput.type = confirmation.type = event.target.checked ? 'text' : 'password';
  });
  generate.addEventListener('click', () => {
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
    const passphrase = Array.from(crypto.getRandomValues(new Uint8Array(32)), byte => alphabet[byte & 63]).join('');
    passphraseInput.value = confirmation.value = passphrase;
    status.textContent = 'Strong passphrase generated. Use “Show passphrase” to save it somewhere safe before publishing.';
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    status.classList.remove('error');
    let token = tokenInput.value.trim(), passphrase = passphraseInput.value;
    if (!/^github_pat_[A-Za-z0-9_]+$/.test(token)) {
      status.textContent = 'Enter a fine-grained GitHub token beginning with github_pat_.';
      status.classList.add('error'); return;
    }
    if (passphrase.length < 24 || passphrase.length > 4096 || passphrase !== confirmation.value) {
      status.textContent = 'Use at least 24 characters and make sure both passphrases match.';
      status.classList.add('error'); return;
    }
    submit.disabled = generate.disabled = true;
    tokenInput.disabled = passphraseInput.disabled = confirmation.disabled = true;
    try {
      status.textContent = 'Checking repository access with GitHub…';
      await PlateGitHub.createClient(token).validate();
      status.textContent = 'Encrypting in your browser…';
      const envelope = await PlateGitHub.encryptToken(token, passphrase);
      token = passphrase = '';
      tokenInput.value = '';
      status.textContent = 'Publishing the encrypted credential to GitHub…';
      const response = await fetch('/config', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(envelope), cache: 'no-store', redirect: 'error'});
      const result = await response.json();
      if (!response.ok) throw new Error(result.message || 'Publishing failed. Check the repository before retrying.');
      status.textContent = result.message;
      submit.textContent = 'Uploads enabled';
      // Keep the passphrase visible to its owner until they close this local page.
    } catch (error) {
      status.textContent = error.message || 'Setup could not finish. Check the connection and try again.';
      status.classList.add('error');
      submit.disabled = false;
    } finally {
      token = passphrase = '';
      generate.disabled = tokenInput.disabled = passphraseInput.disabled = confirmation.disabled = false;
    }
  });
})();
