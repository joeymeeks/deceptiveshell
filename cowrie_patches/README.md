# Cowrie-side patch for the full-replacement backend

This is the one Cowrie-side change needed for the backend this project
actually ships: Cowrie's own built-in `[llm]` backend
(`src/cowrie/llm/protocol.py`), pointed at this middleware's
`/v1/chat/completions` via `cowrie.cfg` - see the main `README.md` for that
config. No other Cowrie source changes are needed for this backend; this is
the only gap found so far.

## `0001-exit-logout-end-session.patch`

Without this, typing `exit` or `logout` gets sent to the LLM like any other
command - Claude fakes a plausible "logging out" response, but the SSH
session never actually closes. This patches `HoneyPotBaseProtocol.lineReceived`
to end the connection for real on `exit`/`logout` before it ever reaches the
LLM call.

Apply to a Cowrie checkout:

```bash
cd /path/to/your/cowrie/checkout
git apply /path/to/this/cowrie_patches/0001-exit-logout-end-session.patch
cowrie restart
```

Verified to apply cleanly (`git apply --check`) to a fresh clone of
`cowrie/cowrie`. Found and originally fixed by Joey during live testing.
