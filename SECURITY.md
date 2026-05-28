# Security

This integration depends on sensitive values captured from your own Yuno mobile-app traffic. Treat those values like passwords.

Never commit, upload, or share:

- Raw capture files, HAR files, proxy exports, packet captures, or dumps.
- `.env` files.
- Session tokens.
- Encrypted Yuno login payload values.
- Basic Authorization credentials.
- PAN, MPRN, account IDs, names, emails, phone numbers, addresses, or payment details.

The repository `.gitignore` blocks common local secret and capture file patterns. It is still your responsibility to inspect changes before committing.

The integration stores configured values in Home Assistant config entry storage and avoids logging them. Debug logs should not include request headers, request bodies, or API responses.

Do not implement or use certificate-pinning bypasses, app attestation bypasses, DRM circumvention, or binary patching for this project.

Report security issues privately to the repository owner. Do not open public issues containing secrets or account data.
