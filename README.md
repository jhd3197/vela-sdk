# Vela SDK

Download the SDK tarball from [GitHub Releases](https://github.com/jhd3197/vela-sdk/releases/latest). Plain HTML apps load the engine-served
script with `<script src="_vela/sdk.js"></script>`. The script exposes `Vela`.
No hub bearer credential or app bearer credential is sent into the frame.

```js
const context = await Vela.ready;
const document = await Vela.storage.read();
const saved = await Vela.storage.write({ text: 'Hello' }, document.revision);
Vela.onSave(async () => {
  // Persist the app's current draft, then resolve. Reject on failure.
  await Vela.storage.write({ text: editor.value }, saved.revision);
});
await Vela.setUnsavedChanges(true);
Vela.onContext(context => {
  // Avoid context.viewport.hostControl, a reserved rectangle in frame pixels.
});
await Vela.navigation.returnToApps();
```

Storage is one revisioned JSON document per installation's app data. Missing data
returns `{value: null, revision: 0, schemaVersion: 1}`. Writes require the revision
read by the client. A stale revision returns 409; read and reconcile explicitly.
Never blindly retry writes against a new revision. Errors carry `message` and
HTTP `status` when supplied by the host. Default quota is 1 MiB, maximum 10 MiB.
Uninstall preserves data; reinstall creates a new identity and reattaches that
app's retained document. Schema changes fail closed pending a migration.

`context` contains installation identity, protocol, granted capabilities, theme,
locale, view mode and viewport dimensions/insets/reserved host-control rectangle.
`onContext` returns an unsubscribe function. `onSave` registers the app's save
handler; `setUnsavedChanges` informs host navigation. Close/return only close the
view. The host can discard and leave if saving times out. Browser refresh/close
uses the browser's native unsaved-work warning.

Protocol 1 uses a `vela:ready`/`vela:init` handshake, source-window and origin
checks, a fresh nonce per view, request IDs, an operation allowlist, and timeouts.
The host requires the frame's origin to be `null` (an opaque sandbox origin).
Opaque origin alone is **not** identity: source window and nonce must also match.
The host bridge lives in Vela's `web/src/bridge/host.js` and stays in the hub bundle. Do not ship it inside an app.
App sessions expire after one hour and are revoked when the view closes or the
app is uninstalled. Reopen a view to obtain a fresh session.

## Changes that need a person

Most requests answer in milliseconds, and the SDK gives them ten seconds before
deciding the host is not there. Some do not: when an app runs on a Vela desktop
an agent is working in, a change may need the server's owner to approve it, and
that is a person walking back to their computer rather than a slow response.

The SDK announces an `approvals` feature in its handshake. A host that supports
it answers such a request with `vela:pending` instead of a result, the SDK
extends that request's deadline to the one Vela set on the question, and the
original promise stays open. It resolves with the real result once the change is
made, or rejects with `status` 403 when the owner said no and 409 when the
request expired or was cancelled. A host that does not know the feature, or an
older SDK that does not announce it, behaves exactly as before — the protocol
number is unchanged.

```js
Vela.onApprovalNeeded(({ summary, expiresAt }) => {
  banner.textContent = summary.headline; // "Notes wants to save a change."
});
try {
  await Vela.storage.write(draft, revision);
} catch (error) {
  if (error.status === 403) banner.textContent = 'That change was not approved.';
}
```

`onApprovalNeeded` is for display only, and `Vela.waitingForApproval` says
whether anything currently is. Nothing an app does approves anything: a request
is resolved by the owner, in Vela's own controls, on a route no app session can
reach. If the app's own deadline passes first the SDK tells the host to withdraw
the question, so a prompt is never left on somebody's screen with nothing behind
it — and an answer given after that point resolves nothing.

Design an app so that a refused or expired change is survivable: keep the draft,
say what happened, and let the person retry. Where an operation can be expressed
as a declared action, prefer that — it is validated, receipted, and safe to
retry with the same request key.

The SDK also provides `storage.backup()`, `storage.snapshots()`,
`storage.restore(snapshotId, expectedRevision)` and `storage.export()` (downloads
the saved document through the host). Restore requires the current revision and
creates a recovery snapshot before replacing data. Snapshots are app-scoped.

Apps with the `connections` grant and an Ollama operation declaration can use
`connections.status()` and `connections.invoke('models.list')`,
`connections.invoke('server.version')`, or
`connections.invoke('models.show', {model: 'model:tag'})`. Binding the server is
a hub-owned action; apps cannot choose URLs or invoke server lifecycle operations.

Health uses the app-declared legacy import UI in the hub. General automatic
schema migrations and offline writes are not implemented. Legacy v1 apps retain
trusted same-origin behavior until explicitly migrated.

## App actions (SDK 0.5)

Declare the `actions` capability and an exact `actionRequests` entry such as
`{app: 'notes', action: 'create-note'}`. The user separately allows that action in
the host controls; installing an app does not create an inter-app grant.

```js
const available = await Vela.actions.list();
// Persist key and input in your own app data BEFORE attempting the action.
const receipt = await Vela.actions.invoke('notes', 'create-note',
  { title: 'Dinner plan', body: 'Monday: pasta' }, savedOutboxKey);
```

Always reuse the persisted key and exact input when retrying an uncertain result.
Successful retries return the original receipt with `replayed: true`; changed
input under the same key returns 409. A deliberate new action needs a new key.
The engine atomically writes the target record and receipt. Replays are historical
receipts: they do not recreate a note later deleted or removed by rollback.

Providers declare app-local input/output schemas and the `storage.append`
handler. It copies named input fields into a new record, adds engine-generated
`id` and `updated`, validates the complete target document, and returns only
`{recordId, revision}`. There are no arbitrary scripts, reads or proxy calls.
Both installation identities and manifest fingerprints bind grants; changes
require fresh host approval. Calls have a two-second transaction deadline and
32 KiB input limit. The host shows metadata-only success/failure activity.

## Desk widgets

Declare the `widgets` capability and up to four `widgets` entries in the
manifest, then publish a summary for one of them whenever the app has something
new to say:

```js
await Vela.widgets.publish('sync', {
  value: '73',
  unit: 'changes',
  caption: 'queued since 02:14',
  attention: true,
});
```

The host renders the summary with its own components, always labelled with the
app it came from; no app code runs on the desk. A summary is a flat JSON object
of at most 4 KB: `value`, `unit`, `delta` and `caption` are strings of at most
200 characters, `progress` is 0-100, `rows` is up to eight `{label, detail}`
pairs, `actions` is up to three `{action, label}` naming the app's own granted
actions, `attention` is a boolean the rail reads, and `expiresAt` is an ISO 8601
timestamp after which the host marks the summary stale. Anything else is
refused: 403 without the grant, 422 for an unknown widget id or a bad field, 413
over the size limit. Publishing `{}` is valid and means "nothing to report yet".
Summaries are removed when the app is uninstalled.

## Downloads

[GitHub Releases](https://github.com/jhd3197/vela-sdk/releases/latest) contain the
portable npm tarball and its checksum. These are GitHub downloads; npm registry
publication is not enabled. The `@vela` scope must be confirmed before an npm release.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md),
[CONTRIBUTORS.md](CONTRIBUTORS.md) and [SECURITY.md](SECURITY.md).

## Support Vela

Vela is free and open source. If it saves you time, you can help keep it going:

- ⭐ [Star the repo](https://github.com/jhd3197/vela) — it costs nothing and helps a lot
- 💖 [GitHub Sponsors](https://github.com/sponsors/jhd3197)
- ☕ [Buy Me a Coffee](https://buymeacoffee.com/jhd3197)

### 💎 Crypto

| | Asset | Network | Address |
|:---:|---|---|---|
| <img src="docs/images/funding/usdt-trc20.png" width="110" alt="QR code for the USDT TRC-20 donation address" /> | **USDT** | **TRC-20** · Tron | `TTiCtqLauF1iSW2YGB3b78KmRxRqoLCgeL` |
| <img src="docs/images/funding/usdt-erc20.png" width="110" alt="QR code for the USDT and ETH ERC-20 donation address" /> | **USDT / ETH** | **ERC-20** · Ethereum | `0xD13D5355Fa214e8317fea2ff192a065BaeC13527` |
| <img src="docs/images/funding/btc.png" width="110" alt="QR code for the Bitcoin donation address" /> | **BTC** | **Bitcoin** | `bc1qatx67n3qxdvuv3arc9j8aytk34f22g02k9c7vr` |
| <img src="docs/images/funding/sol.png" width="110" alt="QR code for the Solana donation address" /> | **SOL** | **Solana** | `AWXzqtBEgUfteHPQtDegsZ6D5y57M3GGdKPD8rR7h6xu` |

## License

[MIT](LICENSE). Created and maintained by [Juan Denis](https://github.com/jhd3197).
