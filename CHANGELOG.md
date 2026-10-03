# Changelog

## Unreleased

### Added

- **`Vela.surfaces.open({ source, title? })`.** An app with the `surfaces`
  capability can open a desktop window that draws a surface document fetched
  through its own `http` connection. The app supplies only a
  connection-relative `source` path, which the host validates against the
  connection's manifest path rules, and an optional `title`; the host fills in
  the calling app's id, fetches the JSON document itself, and draws the
  window — data, never markup.

- **`Vela.navigation.openLink(url)`.** An app with an `http` connection can
  open an https link on that service's site in a new browser tab, such as a
  pull request on `github.com` for an app connected to `api.github.com`. The
  host refuses links to any other site.

- **`Vela.topbar.publish(items)`.** An app with the `topbar` capability can put
  up to three small status items in Vela's top bar while its window is open — a
  temperature, a queue depth, a connection state. Each item is
  `{ id, icon?, label?, title?, tone? }`: plain data, drawn by the host from its
  own icon set, never markup and never a URL. Publishing replaces the previous
  list, so an empty array takes the items down, and closing the window takes
  them down as well. Like widgets, the items are not persisted: republish them
  from `Vela.ready`. Whether the capability was granted is already in
  `Vela.context.capabilities`; a host that does not support the verb answers
  the request with "Operation is not granted" rather than failing the app.

- **A request can wait for a person.** Ten seconds is right for "the host is
  there"; it is wrong for "somebody has been asked whether this change may
  happen". The SDK now announces an `approvals` feature in its handshake, and a
  host that supports it answers `vela:pending` for a request that needs the
  owner's decision. The app's promise stays open, with a deadline taken from the
  one Vela set on the question itself, and resolves when the change is made or
  rejects with the reason it was not. `Vela.onApprovalNeeded(callback)` lets an
  app show "waiting for approval" rather than appearing to hang, and
  `Vela.waitingForApproval` says whether anything currently is. When the app's
  own deadline does pass, it tells the host to withdraw the question rather than
  leaving a prompt on somebody's screen with nothing behind it.

  Nothing here approves anything: the callback is for display, and only the
  owner can resolve a request, in Vela's own controls, on a route no app session
  can reach. A host that does not know the feature never sends `vela:pending`,
  and an SDK older than this one is never sent it — the protocol number does not
  change and existing apps behave exactly as before.

- `Vela.widgets.publish(id, summary)` for apps that declare the `widgets`
  capability: publishes a small JSON summary of one declared widget, which the
  Vela desk renders with its own components. See "Desk widgets" in the README
  for the payload and its limits.

## 0.5.0 - 2026-09-14

### Added

- Browser SDK for secure Vela app storage, connections and actions.
- Independent GitHub downloads, artifact checks and automatic releases after main updates.
- Contributor, security and funding information with shared changelog instructions.
