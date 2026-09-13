# Account authentication

The login protocol was checked against the Yuno Energy Android 4.3 app and a
successful login to the account owner's API on 10 September 2026. Billing and
usage endpoints returned HTTP 200. The owner uses the iPhone app; an Android-origin
request successfully accessed the same account. Tests committed here contain
synthetic inputs only. No APK, customer account export, or real login values are
included in this repository.

The Android app encrypts the lowercased email and unchanged password using
`Cipher.getInstance("RSA")`. Android's Bouncy Castle provider maps this bare
transformation to `CipherSpi$NoPadding`. Desktop Java's SunJCE provider defaults
to PKCS#1 v1.5 instead; that initially produced Yuno error 1004 even for correct
credentials. Changing the client to match the Android format resolved the login.

The public modulus, client identification and signing constants in
`yuno_api/auth.py` come from that app's distributed client. Encryption preserves
the 64-byte RSA output, including leading zero bytes, before base64 encoding.
The server's private key is neither needed nor recovered. This is compatibility
with an existing HTTPS protocol, not an encryption design for new applications.

Primary references:

- [Android Bouncy Castle RSA registration](https://android.googlesource.com/platform/external/bouncycastle/+/refs/heads/main/repackaged/bcprov/src/main/java/com/android/org/bouncycastle/jcajce/provider/asymmetric/RSA.java)
- [Android Conscrypt registrations](https://android.googlesource.com/platform/external/conscrypt/+/refs/heads/main/common/src/main/java/org/conscrypt/OpenSSLProvider.java)

`tests/fixtures/rsa_no_padding.json` was generated with Bouncy Castle 1.78.1's bare
RSA and independently checked against SunJCE's explicit `RSA/ECB/NoPadding`.
It contains only synthetic text and its public-key ciphertext.

The request signature covers the exact POST body, or the `/api/` path for a GET.
Generated login values use compact JSON to match Home Assistant's `json_dumps`,
which it supplies as the serializer for the original integration's aiohttp session.
Plain Python `json.dumps` adds spaces and would produce a different signature.
The regression test compares our bytes with Home Assistant's actual serializer. The integration sends those pre-signed
bytes directly, so serializer changes cannot silently invalidate the signature.
Legacy manually supplied entries retain their original JSON request path.

Account setup discards the plain password and stores the encrypted credentials,
request values, and issued session token in Home Assistant's config entry.
Encrypted login values remain reusable credentials; they are not password hashes.
An authentication failure permits one login, then one usage request. Other server
or network failures do not trigger a login. Replacement tokens are persisted
before the next poll and reused after restart. Reauthentication only attempts a
login after the user submits the form.

The tests pass against Home Assistant 2024.12.5 (Python 3.12) and 2026.9.1
(Python 3.14). CI covers both Python versions.

The integration tests use Home Assistant's real config flow and coordinator
interfaces with fake network responses. They do not log into Yuno. The account owner also installed the integration on their Home Assistant
instance and reported successful setup. The earlier live protocol check used the
standalone account client.
