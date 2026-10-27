import ast, glob, json, re
LOG = "/home/cowrie/cowrie/var/log/cowrie/"
conns, logged = [], set()
for f in sorted(glob.glob(LOG + "cowrie.json*")):
    for line in open(f):
        try: e = json.loads(line)
        except ValueError: continue
        if e.get("eventid") == "cowrie.session.connect":
            conns.append((e["timestamp"], e.get("src_ip"), e["session"]))
        elif e.get("eventid") == "cowrie.command.input":
            logged.add((e["session"], e.get("input")))
conns.sort()
pat = re.compile(r'^(\S+) \[SSHChannel session \(\d+\) on SSHService .*?HoneyPotSSHTransport,\d+,([\d.]+)\] Executing command "(b.*)"$')
out = []
for f in sorted(glob.glob(LOG + "cowrie.log*")):
    for line in open(f, errors="replace"):
        m = pat.match(line.rstrip("\n"))
        if not m: continue
        ts, ip, raw = m.groups()
        try: cmd = ast.literal_eval(raw).decode("utf8", errors="replace")
        except Exception: continue
        sid = None
        for cts, cip, csid in conns:
            if cip == ip and cts <= ts: sid = csid
        if sid is None or (sid, cmd) in logged: continue
        out.append({"eventid": "cowrie.command.input", "session": sid, "src_ip": ip,
                    "timestamp": ts, "input": cmd, "message": "CMD: " + cmd[:200],
                    "recovered_from": "cowrie.log", "sensor": "llm-vm"})
with open("/home/cowrie/recovered_exec_commands.json", "w") as fh:
    for r in out: fh.write(json.dumps(r) + "\n")
print(f"recovered {len(out)} one-shot commands from {len({r['session'] for r in out})} sessions")
