# Recovery Policy

The recovery manager accepts the recommendation from the deterministic diagnosis engine. It does not permit the ML classifier to initiate an action.

- **No fault:** no action is required.
- **One supported fault:** execute the corresponding simulated sensor, communication or task recovery action.
- **Verification:** require the configured number of consecutive healthy observations before returning to normal mode.
- **Retry:** if verification fails, wait for a configurable retry-backoff interval before the next bounded attempt.
- **Escalation:** after the configured maximum attempts, enter safe mode.
- **Compound fault:** choose containment rather than attempting multiple isolated recoveries in an ambiguous dependency state.

Safe-mode containment on compound faults and exhausted attempts is a mandatory project guardrail. All actions in this repository modify simulator state only; they do not reset physical hardware.
