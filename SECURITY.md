# Security

Report vulnerabilities through [private vulnerability reporting](https://github.com/jhd3197/vela-sdk/security/advisories/new).
If unavailable, use [the maintainer's website](https://juandenis.com) to request
a private channel. Do not post exploit details, credentials or personal app data
in public issues. Include the affected component and Vela versions, reproduction
steps and impact. Fixes target the current development branch; no stable support
window or response deadline has been promised.

Review app permissions and release sources. App releases use Vela's v2 capability
and storage boundaries; downloading source does not grant permission to another
app's data. A checksum verifies bytes against its trusted pin, not publisher identity.
See [Vela's security model](https://github.com/jhd3197/Vela/blob/main/SECURITY.md).
