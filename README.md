# DeceptiveShell

**An LLM-Powered Adaptive Honeypot**

DeceptiveShell extends the [Cowrie](https://github.com/cowrie/cowrie) SSH honeypot with a
large language model that makes up realistic shell output for commands Cowrie can't handle.
We run it alongside an unmodified Cowrie honeypot and measure whether AI-driven deception
captures more attacker behavior than a scripted honeypot.

> ⚠️ **Research software.** This project deliberately attracts real attackers. Only deploy it
> on isolated, disposable infrastructure with egress filtering. Never run it on a home,
> campus, or production network.

---

## The Problem

Honeypots like Cowrie fake a Linux shell using a fixed list of built-in commands. Anything
outside that list returns `command not found`. Attackers test for this, recognize the
honeypot, and disconnect, which leaves defenders with short, low-value sessions.

## Our Approach

Cowrie has a built-in `[llm]` backend mode: instead of its normal fixed command set, it sends
*every* command the attacker types to an OpenAI-compatible API and returns the response as the
terminal output. We point that at our own middleware instead of OpenAI directly, which adds a
locked-down persona prompt, response caching, and per-session fake filesystem tracking (current
directory, created files) so the LLM can't contradict itself later in the same session.

This is a config-only integration - Cowrie's own source code is never modified, aside from one
small required patch (`exit`/`logout` ending the session for real instead of going to the LLM),
documented in `cowrie_patches/`.

## Research Question

> Does an AI-driven honeypot keep attackers engaged longer and reveal more of their behavior
> than a traditional scripted one?

We run both honeypots at the same time and compare them on:

| Metric | What it measures |
|---|---|
| Session length | How long attackers stay |
| Commands per session | How much behavior we capture |
| Engagement depth | Recon only, or downloads and privilege escalation |
| Attacker drop-off | When they leave, and after which command |

---

## How It Works

```
Attacker ──SSH──▶ Cowrie's [llm] backend ──▶ DeceptiveShell middleware ──▶ Claude API
                                                     │                          │
                                              cache + per-session       raw terminal
                                              fake filesystem state    output, no chat
                                                     │                          │
                                                     └────────── Output sent back ─────┘
                                                                  to attacker
```

- **Integration point:** `cowrie.cfg`'s `[honeypot] backend = llm` + `[llm] host`/`path`
  pointed at this middleware - see `app/README` setup below. The one Cowrie-side source
  change still needed (`exit`/`logout` ending the session for real instead of going to the
  LLM) is in `cowrie_patches/`.
- **Caching:** keyed on session + current fake directory + the exact command, so a repeat
  doesn't cost another API call or risk a different answer the second time.
- **Session-state tracking:** Cowrie's own `[llm]` backend never tracks a fake filesystem
  itself - this middleware does, parsing the attacker's username out of Cowrie's own system
  prompt text (no Cowrie config changes needed for that part) since Cowrie never sends a real
  session ID.
- **Fallback:** if the API fails, the middleware returns an error rather than silently making
  something up.

---

## Tech Stack

- **Honeypot:** Cowrie (Python, Twisted)
- **LLM:** Anthropic Claude API
- **Infrastructure:** AWS EC2, Ubuntu Server 26.04 LTS, t3.small
- **Language:** Python 3

---

## Setup

### Prerequisites
- A working Cowrie install ([Cowrie docs](https://docs.cowrie.org/))
- Python 3.10+
- An Anthropic API key

### Install
```bash
git clone https://github.com/[username]/[repo-name].git
cd [repo-name]
pip install -r requirements.txt
```

### Configure
Create a `.env` file (**never commit it**):
```
ANTHROPIC_API_KEY=your-key-here
```

### Integrate with Cowrie
1. Apply `cowrie_patches/0001-exit-logout-end-session.patch` to your Cowrie checkout (required -
   without it, typing `exit` sends to the LLM instead of actually ending the session). See
   `cowrie_patches/README.md`.
2. In `cowrie.cfg`:
   ```ini
   [honeypot]
   backend = llm

   [llm]
   host = http://localhost:8000
   path = /v1/chat/completions
   api_key = not-needed
   model = claude-sonnet-5
   max_tokens = 500
   temperature = 0.7
   ```
3. Restart Cowrie: `cowrie restart`

### Test
```bash
ssh -p 2222 root@localhost
```
Type any command - since the `[llm]` backend replaces Cowrie's whole shell, everything
(`ls`, `pwd`, `vmstat`, anything) goes through the LLM. If you get believable output and a
prompt afterward, it's working. Also try `cd somewhere`, then `pwd` on the next line, to confirm
the fake filesystem state actually persists across commands.

---

## Safety and Ethics

- Hosted on an **isolated cloud VM**, never campus or personal networks
- **Egress filtering** keeps the honeypot from being used to attack others
- Runs as a **non-root** service account; admin SSH is limited to team IPs
- Captured data (attacker IPs, passwords) is **kept private and not committed** to this repo
- Any captured malware is analyzed **statically only** and never executed
- Project approved by course instructor

---

## Project Status

| Milestone | Status |
|---|---|
| Cloud VM provisioned and secured | ✅ Complete |
| Baseline Cowrie running, logging verified | ✅ Complete |
| LLM validated (7/7 shell commands stayed in character) | ✅ Complete |
| Middleware written (caching + session-state tracking) | ✅ Complete |
| Automated tests for middleware logic (27 passing) | ✅ Complete |
| Cowrie `[llm]` backend wired to the middleware + exit/logout patch | ✅ Complete |
| Full live test on the actual deployment VM | 🔲 Not started |
| Red-team testing and hardening | 🔲 Not started |
| Live deployment and data collection | 🔲 Not started |
| Analysis, paper, and presentation | 🔲 Not started |

---

## Team

| Name | Role |
|---|---|
| Joey Meeks | Security Lead: threat model, probe testing, analysis |
| Shiva Patel | Build Lead: middleware, integration, deployment |
| Cole Belew | Evaluation: data analysis, comparison, write-up |

**Course:** [CSI 495]
**Institution:** [University of Tennessee at Martin]

---

## Acknowledgments

Built on [Cowrie](https://github.com/cowrie/cowrie) by Michel Oosterhof and contributors
(BSD-3-Clause license).
