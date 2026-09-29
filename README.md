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

We hook into the point where Cowrie fails to find a command and send that command to an LLM
instead. The generated output goes back into the live session, so the attacker sees a shell
that responds believably to anything they type.

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
Attacker ──SSH──▶ Cowrie ──▶ Is the command built in?
                                  │
                        ┌─────────┴─────────┐
                       Yes                   No
                        │                     │
                 Cowrie's output      DeceptiveShell middleware
                                              │
                                        LLM (Claude API)
                                              │
                                   Output sent back to attacker
```

- **Integration point:** the `if not cmdclass:` branch in `HoneyPotShell._run_expanded()`
  (`src/cowrie/shell/honeypot.py`)
- **Non-blocking:** the LLM call runs with `deferToThread` so a slow API response doesn't
  freeze other sessions
- **Fallback:** if the API fails or times out, the honeypot falls back to Cowrie's normal
  `command not found` behavior

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
1. Copy the middleware into Cowrie's `src/` folder
2. Add the hook to `src/cowrie/shell/honeypot.py` at the `if not cmdclass:` branch
3. Restart Cowrie: `cowrie restart`

### Test
```bash
ssh -p 2222 root@localhost
```
Type a command Cowrie doesn't implement, like `vmstat` or `lsof`. If you get made-up output
and a prompt afterward, it's working.

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
| Middleware written | ✅ Complete |
| Middleware integrated with Cowrie | 🔲 In progress |
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
