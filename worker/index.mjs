const MAX_EMAIL_BYTES = 25 * 1024 * 1024;

export default {
  async fetch(request, env) {
    // HTTP serves only the portfolio. Email objects have no public HTTP route.
    return env.ASSETS.fetch(request);
  },

  async email(message, env) {
    if (message.to.toLowerCase() !== 'randy@randykleckner.com') {
      message.setReject('Unknown recipient');
      return;
    }
    if (!Number.isSafeInteger(message.rawSize) || message.rawSize > MAX_EMAIL_BYTES) {
      message.setReject('Message exceeds the 25 MiB storage limit');
      return;
    }
    // Bound buffering explicitly; do not rely solely on the declared rawSize.
    const reader = message.raw.getReader();
    const chunks = [];
    let size = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > MAX_EMAIL_BYTES) {
          await reader.cancel();
          message.setReject('Message exceeds the 25 MiB storage limit');
          return;
        }
        chunks.push(value);
      }
    } finally {
      reader.releaseLock();
    }
    const raw = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { raw.set(chunk, offset); offset += chunk.byteLength; }
    const digest = await crypto.subtle.digest('SHA-256', raw);
    const id = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    // A retry of the same raw message uses the same key rather than creating duplicates.
    // Await persistence so a storage failure cannot be acknowledged as success.
    await env['job-mail-inbound'].put(`inbox/${id}.eml`, raw, {
      httpMetadata: { contentType: 'message/rfc822' },
      customMetadata: {
        envelopeFrom: message.from,
        envelopeTo: message.to,
        receivedAt: new Date().toISOString(),
      },
    });
  },
};
