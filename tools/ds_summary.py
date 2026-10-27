import json, collections, glob
events = []
for f in sorted(glob.glob('/home/cowrie/cowrie/var/log/cowrie/cowrie.json*')):
    for line in open(f):
        try: events.append(json.loads(line))
        except ValueError: pass
S = collections.defaultdict(lambda: {"ip": "", "start": "", "dur": 0.0, "cmds": [], "login": False})
creds, cmds, dls = collections.Counter(), collections.Counter(), []
for e in events:
    sid, ev = e.get("session"), e.get("eventid", "")
    s = S[sid]
    if ev == "cowrie.session.connect": s["ip"], s["start"] = e.get("src_ip", ""), e["timestamp"][:16].replace("T", " ")
    elif ev == "cowrie.login.success": s["login"] = True; creds[(e.get("username"), e.get("password"))] += 1
    elif ev == "cowrie.login.failed": creds[(e.get("username"), e.get("password"))] += 1
    elif ev == "cowrie.command.input": s["cmds"].append(e.get("input", "")); cmds[e.get("input", "")] += 1
    elif ev == "cowrie.session.closed": s["dur"] = float(e["duration_ms"]) / 1000 if "duration_ms" in e else float(e.get("duration", 0) or 0)
    elif ev == "cowrie.session.file_download": dls.append(e.get("url", ""))
logged = [s for s in S.values() if s["login"]]
active = [s for s in logged if s["cmds"]]
avg = lambda xs: sum(xs) / len(xs) if xs else 0
print("=== DECEPTIVESHELL PROGRESS ===")
print(f"Connections:         {len(S)}")
print(f"Unique attacker IPs: {len({s['ip'] for s in S.values()})}")
print(f"Successful logins:   {len(logged)}")
print(f"Sessions w/ commands:{len(active)}")
print(f"Total commands:      {sum(cmds.values())}")
print(f"Avg session length:  {avg([s['dur'] for s in logged]):.1f} s (logged-in sessions)")
print(f"Avg commands/session:{avg([len(s['cmds']) for s in active]):.1f} (sessions with commands)")
print(f"Download attempts:   {len(dls)}")
print("\n--- Top 10 commands ---")
for c, n in cmds.most_common(10): print(f"{n:5}  {c[:90]}")
print("\n--- Top 10 username/password pairs ---")
for (u, p), n in creds.most_common(10): print(f"{n:5}  {u} / {p}")
print("\n--- Last 10 sessions with commands ---")
for s in sorted(active, key=lambda s: s["start"])[-10:]:
    print(f"{s['start']}  {s['dur']:6.1f}s  {len(s['cmds']):3} cmds  last: {s['cmds'][-1][:50]}")
