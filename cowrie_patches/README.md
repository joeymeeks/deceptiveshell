# Cowrie-side patch for the full-replacement backend

These are the Cowrie-side changes needed for the backend this project
actually ships: Cowrie's own built-in `[llm]` backend
(`src/cowrie/llm/protocol.py`), pointed at this middleware's
`/v1/chat/completions` via `cowrie.cfg` - see the main `README.md` for that
config. No other Cowrie source changes are needed for this backend; these are
the only gaps found so far.

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

## `0002-exec-command-logging.patch`

Without this, one-shot exec commands (`ssh host 'cmd'`, which is how most
bots run their scripts) are sent to the LLM and answered, but never logged
as `cowrie.command.input` in `cowrie.json`. The shell backend does log them,
so the LLM honeypot's command counts were under-reported. This patches
`HoneyPotExecProtocol.connectionMade` to dispatch `cowrie.command.input`
before the rate-limit check, so every exec command is logged, including
ones the limiter blocks.

Apply to a Cowrie checkout (after `0001`):

```bash
cd /path/to/your/cowrie/checkout
git apply /path/to/this/cowrie_patches/0002-exec-command-logging.patch
cowrie restart
```

Found in live data and applied to the deployed LLM VM on Oct 23, ~15:54 UTC.
Exec commands from before that time were recovered from `cowrie.log` with
`tools/recover_exec.py`.
