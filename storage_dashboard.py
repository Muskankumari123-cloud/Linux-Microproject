#!/usr/bin/env python3
"""Storage Monitor dashboard. Run: python3 storage_dashboard.py  then open http://localhost:8765
Reads the real files from ~/storage-monitor (scripts, logs, reports). Standard library only."""
import glob, json, os, platform, re, subprocess, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.expanduser("~/storage-monitor")
SCR, LOGS, REP = BASE + "/scripts", BASE + "/logs", BASE + "/reports"
CFG = SCR + "/config.sh"
SCRIPTS = {"disk": "disk_monitor.sh", "inode": "inode_monitor.sh",
           "growth": "growth_monitor.sh", "report": "report.sh"}

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

def pct(s):
    s = s.strip().strip("%")
    return int(s) if s.isdigit() else 0

def thresholds():
    t = {"disk": 80, "inode": 80, "growth": 500}
    try:
        for line in open(CFG):
            m = re.match(r"(DISK|INODE|GROWTH)_THRESHOLD=(\d+)", line)
            if m: t[m.group(1).lower()] = int(m.group(2))
    except OSError:
        pass
    return t

def volumes():
    v = []
    if platform.system() == "Darwin":
        for l in sh("df -k").splitlines()[1:]:
            p = l.split(None, 8)
            if len(p) == 9 and p[0].startswith("/dev/"):
                v.append(dict(mount=p[8], disk=pct(p[4]), inode=pct(p[7]),
                              used=int(p[2]) * 1024, size=int(p[1]) * 1024))
    else:
        ino = {}
        for l in sh("df -iP").splitlines()[1:]:
            p = l.split(None, 5)
            if len(p) == 6: ino[p[5]] = pct(p[4])
        for l in sh("df -kP").splitlines()[1:]:
            p = l.split(None, 5)
            if len(p) == 6 and p[0].startswith("/dev/"):
                v.append(dict(mount=p[5], disk=pct(p[4]), inode=ino.get(p[5], 0),
                              used=int(p[2]) * 1024, size=int(p[1]) * 1024))
    return sorted(v, key=lambda x: -x["disk"])

def read_lines(path, n):
    try:
        return open(path).read().splitlines()[-n:]
    except OSError:
        return []

def status():
    hist = []
    for l in read_lines(LOGS + "/usage_history.csv", 30):
        a = l.split(",")
        if len(a) == 2 and a[1].isdigit(): hist.append([a[0], int(a[1])])
    reports = sorted(os.path.basename(p) for p in glob.glob(REP + "/report_*.txt"))[::-1]
    return dict(host=platform.node(), volumes=volumes(), thresholds=thresholds(), history=hist,
                alerts=read_lines(LOGS + "/alerts.log", 40)[::-1], reports=reports)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, body, ctype="application/json", code=200):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/": return self.send(PAGE, "text/html")
        if u.path == "/api/status": return self.send(json.dumps(status()))
        if u.path == "/api/report":
            name = os.path.basename(parse_qs(u.query).get("name", [""])[0])
            try: return self.send(open(REP + "/" + name).read(), "text/plain")
            except OSError: return self.send("Report not found.", "text/plain", 404)
        self.send("Not found", "text/plain", 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/run":
            f = SCRIPTS.get(data.get("script"))
            if not f: return self.send("Unknown script", "text/plain", 400)
            try:
                r = subprocess.run([SCR + "/" + f], cwd=SCR, capture_output=True, text=True, timeout=300)
                out = (r.stdout + r.stderr).strip() or "Done."
            except Exception as e:
                out = "Could not run %s: %s" % (f, e)
            return self.send(json.dumps({"output": out}))
        if self.path == "/api/config":
            txt = open(CFG).read()
            for k in ("disk", "inode", "growth"):
                if str(data.get(k, "")).isdigit():
                    txt = re.sub(r"(?m)^%s_THRESHOLD=\d+" % k.upper(), "%s_THRESHOLD=%d" % (k.upper(), int(data[k])), txt)
            open(CFG, "w").write(txt)
            return self.send(json.dumps(thresholds()))
        self.send("Not found", "text/plain", 404)

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Storage Monitor</title>
<style>
:root{--bg:#e9eef1;--panel:#f8fafb;--ink:#12303a;--mute:#5d7580;--line:#cdd9de;--ok:#2e8b57;--warn:#d8921a;--bad:#c4372d;--accent:#0f5c6e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Avenir Next",system-ui,sans-serif}
header{padding:28px 32px 8px}h1{margin:0;font-size:28px;font-weight:650;letter-spacing:-.01em}
.sub{color:var(--mute);margin-top:2px}.state{margin-top:14px;font-size:20px;font-weight:600}
.state.bad{color:var(--bad)}.state.ok{color:var(--ok)}
main{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:20px;padding:16px 32px 40px}
@media(max-width:900px){main{grid-template-columns:1fr;padding:12px 16px}header{padding:20px 16px 4px}}
section{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:18px 20px;margin-bottom:20px}
h2{margin:0 0 12px;font-size:16px;font-weight:650}
.vol{padding:10px 0;border-top:1px solid var(--line)}.vol:first-of-type{border-top:0}
.vh{display:flex;justify-content:space-between;gap:12px;font-size:14px}.vh b{font-weight:600;word-break:break-all}
.vh span{color:var(--mute);white-space:nowrap}
.bar{position:relative;height:12px;background:#dbe5e9;border-radius:2px;margin-top:6px}
.fill{height:100%;border-radius:2px;background:var(--ok)}.fill.warn{background:var(--warn)}.fill.bad{background:var(--bad)}
.tick{position:absolute;top:-4px;bottom:-4px;width:2px;background:var(--ink)}
.row{display:flex;flex-wrap:wrap;gap:8px}
button{font:inherit;font-weight:600;padding:8px 14px;border-radius:4px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer}
button.alt{background:transparent;color:var(--accent)}button:disabled{opacity:.5;cursor:wait}
button:focus-visible,input:focus-visible{outline:3px solid #7fc4d4;outline-offset:2px}
label{display:block;font-size:13px;color:var(--mute);margin-top:12px}
input{width:100%;font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:4px;background:#fff;color:var(--ink)}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
pre{margin:12px 0 0;padding:12px;background:#0f2a33;color:#d8ecf1;border-radius:4px;font:12.5px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow:auto}
pre:empty{display:none}
.al{font:12.5px/1.45 ui-monospace,Menlo,monospace;padding:7px 0;border-top:1px solid var(--line);word-break:break-word}
.al:first-of-type{border-top:0}.scroll{max-height:260px;overflow:auto}.empty{color:var(--mute)}
.rep{display:block;width:100%;text-align:left;background:transparent;color:var(--accent);border:0;border-top:1px solid var(--line);border-radius:0;padding:8px 0;font-weight:500}
svg{width:100%;height:90px;display:block}
</style></head><body>
<header><h1>Storage Monitor</h1><div class="sub" id="host"></div><div class="state" id="state">Checking volumes…</div></header>
<main><div>
<section><h2>Volumes</h2><div id="vols"></div>
<div class="sub" style="font-size:13px;margin-top:10px">The dark mark on each bar is your disk threshold.</div></section>
<section><h2>Storage growth</h2><div id="growth"></div></section>
<section><h2>Alert log</h2><div class="scroll" id="alerts"></div></section></div>
<div>
<section><h2>Run a check</h2><div class="row">
<button data-s="disk">Check disk</button><button data-s="inode">Check inodes</button>
<button data-s="growth">Check growth</button><button data-s="report" class="alt">Generate report</button></div>
<pre id="out" aria-live="polite"></pre></section>
<section><h2>Alert thresholds</h2><div class="three">
<div><label for="t-disk">Disk %</label><input id="t-disk" type="number" min="0" max="100"></div>
<div><label for="t-inode">Inode %</label><input id="t-inode" type="number" min="0" max="100"></div>
<div><label for="t-growth">Growth MB</label><input id="t-growth" type="number" min="0"></div></div>
<div class="row" style="margin-top:14px"><button id="save">Save thresholds</button></div></section>
<section><h2>Reports</h2><div id="reps"></div><pre id="view"></pre></section></div></main>
<script>
const $=s=>document.querySelector(s);
const fmt=b=>b>=1e9?(b/1e9).toFixed(1)+" GB":(b/1e6).toFixed(0)+" MB";
const cls=(v,t)=>v>=t?"bad":v>=t*.8?"warn":"";
function bar(v,t){return `<div class="bar"><div class="fill ${cls(v,t)}" style="width:${Math.min(v,100)}%"></div><div class="tick" style="left:${Math.min(t,100)}%"></div></div>`}
async function load(){
  let d;try{d=await (await fetch("/api/status")).json()}catch(e){$("#state").textContent="Dashboard server is not running.";return}
  const t=d.thresholds;$("#host").textContent=d.host;
  const over=d.volumes.filter(v=>v.disk>=t.disk||v.inode>=t.inode);
  const s=$("#state");
  s.textContent=over.length?`${over.length} of ${d.volumes.length} volumes over threshold`:`All ${d.volumes.length} volumes are within limits`;
  s.className="state "+(over.length?"bad":"ok");
  $("#vols").innerHTML=d.volumes.map(v=>`<div class="vol"><div class="vh"><b>${v.mount}</b><span>${v.disk}% used · inodes ${v.inode}%${v.size?" · "+fmt(v.used)+" of "+fmt(v.size):""}</span></div>${bar(v.disk,t.disk)}</div>`).join("")||'<div class="empty">No volumes found.</div>';
  const h=d.history;
  if(h.length<2)$("#growth").innerHTML='<div class="empty">Run “Check growth” twice to see a trend.</div>';
  else{const u=h.map(x=>x[1]),lo=Math.min(...u),hi=Math.max(...u),r=(hi-lo)||1;
    const pts=u.map((x,i)=>`${(i/(u.length-1)*300).toFixed(1)},${(76-(x-lo)/r*68).toFixed(1)}`).join(" ");
    const dm=Math.round((u[u.length-1]-u[u.length-2])/1024);
    $("#growth").innerHTML=`<svg viewBox="0 0 300 84" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="#0f5c6e" stroke-width="2" vector-effect="non-scaling-stroke"/></svg><div class="sub">Last change: ${dm>=0?"+":""}${dm} MB across ${h.length} readings (alert at ${t.growth} MB)</div>`}
  $("#alerts").innerHTML=d.alerts.length?d.alerts.map(a=>`<div class="al"></div>`).join(""):'<div class="empty">No alerts yet.</div>';
  document.querySelectorAll("#alerts .al").forEach((e,i)=>e.textContent=d.alerts[i]);
  $("#reps").innerHTML=d.reports.length?d.reports.map(r=>`<button class="rep" data-r="${r}">${r}</button>`).join(""):'<div class="empty">No reports yet. Generate one above.</div>';
  for(const k of ["disk","inode","growth"]){const i=$("#t-"+k);if(document.activeElement!==i)i.value=t[k]}
}
document.addEventListener("click",async e=>{
  const b=e.target.closest("button");if(!b)return;
  if(b.dataset.s){const o=$("#out");b.disabled=true;o.textContent="Running "+b.textContent.toLowerCase()+"…";
    try{o.textContent=(await (await fetch("/api/run",{method:"POST",body:JSON.stringify({script:b.dataset.s})})).json()).output}catch(x){o.textContent="Run failed: "+x}
    b.disabled=false;load()}
  else if(b.dataset.r){$("#view").textContent="Loading…";$("#view").textContent=await (await fetch("/api/report?name="+encodeURIComponent(b.dataset.r))).text()}
  else if(b.id==="save"){await fetch("/api/config",{method:"POST",body:JSON.stringify({disk:$("#t-disk").value,inode:$("#t-inode").value,growth:$("#t-growth").value})});
    b.textContent="Saved";setTimeout(()=>b.textContent="Save thresholds",1500);load()}
});
load();setInterval(load,10000);
</script></body></html>"""

if __name__ == "__main__":
    if not os.path.isdir(SCR):
        raise SystemExit("Cannot find %s. Create the storage-monitor project first." % SCR)
    srv = ThreadingHTTPServer(("127.0.0.1", 8765), H)
    print("Storage Monitor running at http://localhost:8765  (Ctrl+C to stop)")
    threading.Timer(0.8, lambda: webbrowser.open("http://localhost:8765")).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nStopped.")
