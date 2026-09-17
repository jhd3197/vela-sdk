# Changelog

## Unreleased

### Added

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
