"""Coach Roland dashboard — a nice local web UI for your second monitor.

Runs a tiny local web server. Open it in a browser, drag to monitor 2, fullscreen.
The watcher runs in the background and pushes live reads; the page polls /state and
re-renders. Every recommendation has a hover tooltip explaining WHY (+ a stat slot).

    python -m tftwatch.dashboard          # live (watcher in background; needs game on screen)
    python -m tftwatch.dashboard --demo   # static sample data, no game/API — preview the UI
"""
import sys
import threading

from flask import Flask, jsonify, Response
from dotenv import load_dotenv

from .watcher import watch

load_dotenv()

STATE = {"ts": None, "event": "idle", "data": None, "advice": [], "positioning": []}

_SAMPLE = {
    "ts": "demo", "event": "read",
    "advice": [
        {"text": "AVOID forcing Vex — 3 teams are on it", "severity": "danger",
         "why": "3 teams are contesting Vex. I strongly suggest you do NOT go it — the shared pool "
                "can't feed you, you'll be starved and bottom out. Jhin is the open line; go there.",
         "stat": None},
        {"text": "God: take Kayle (not Thresh)", "severity": "buy",
         "why": "Of the two offered, Kayle gives reliable item value — low-variance and exactly what "
                "your Jhin carry wants. Thresh is all-random; only gamble if you're desperate.",
         "stat": "Realm of the Gods (17.6)"},
        {"text": "Augment: take Advanced Loan", "severity": "buy",
         "why": "Best of the three for a fast-9 board — econ now compounds into hitting Jhin at 8. "
                "Rule: an emblem that points your comp > a proven augment > econ early, combat later.",
         "stat": "augment guidance (live % pending data)"},
        {"text": "EARLY: bridge to Jhin with Caitlyn, Talon, Aatrox, Jax", "severity": "buy",
         "why": "Jhin Fast 9 doesn't come online until level 8-9, so you can't just wait. Play the "
                "Stargazer opener — Caitlyn, Talon, Aatrox, Jax — slam items, win-streak stage 2, and "
                "econ to fast 8, then roll for Jhin.",
         "stat": "metasrc / tftacademy (17.6)"},
        {"text": "BUY Mordekaiser -> cannon to Wisp", "severity": "buy",
         "why": "Wisp is 1 copy from 2-starring Mordekaiser (your team's frontline anchor). Buy any "
                "Mordekaiser you see and send it over the Teamwork Cannon — finishing it beats your gold.",
         "stat": None},
        {"text": "Team D (14 HP) holds Jhin + Aatrox — both yours", "severity": "warn",
         "why": "Team D is about to die. When they bust, Jhin and Aatrox return to the pool — both are "
                "in your plan. DON'T roll now; wait for them to die, then roll into the fuller pool.",
         "stat": None},
    ],
    "positioning": [
        {"text": "Move Rammus to the front", "severity": "warn",
         "why": "Rammus is a tank but it's sitting mid-board. It needs to be on the front line to "
                "soak damage and shield your carries — right now they're exposed.",
         "stat": None},
        {"text": "Put Jhin in a back corner", "severity": "warn",
         "why": "Tuck your carry into a back corner so assassins and divers take the longest to "
                "reach it, buying Jhin more time to deal damage.",
         "stat": "Back-corner carry: longest time-to-death vs divers (meta)"},
    ],
    "mode": "doubleup",
    "data": {
        "players": [
            {"name": None, "team": "A", "is_self": True, "hp": 78, "unit": None, "stars": None},
            {"name": "Wisp", "team": "A", "is_partner": True, "hp": 78, "unit": "Mordekaiser", "stars": 2},
            {"name": "AzAlways", "team": "B", "hp": 64, "unit": "Pyke", "stars": 2},
            {"name": "KAORII", "team": "B", "hp": 64, "unit": None, "stars": None},
            {"name": "VowKeeper", "team": "C", "hp": 90, "unit": None, "stars": None},
            {"name": "Varianna", "team": "C", "hp": 90, "unit": None, "stars": None},
            {"name": "steven mint", "team": "D", "hp": 14, "unit": None, "stars": None, "holds": ["Jhin"]},
            {"name": "toomuchcaffeine", "team": "D", "hp": 14, "unit": None, "stars": None, "holds": ["Aatrox"]},
        ],
        "next_opponent": "Team B",
    },
}

app = Flask(__name__)


@app.route("/state")
def state():
    return jsonify(STATE)


@app.route("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")


def _on_update(update: dict) -> None:
    STATE.update(update)


def main() -> None:
    demo = "--demo" in sys.argv
    if demo:
        STATE.update(_SAMPLE)
        print("Demo mode — open http://127.0.0.1:8765  (sample data, no game/API)")
    else:
        threading.Thread(target=lambda: watch(on_update=_on_update), daemon=True).start()
        print("Live — open http://127.0.0.1:8765  (drag to monitor 2, fullscreen). Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=8765, debug=False)


INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Coach Roland</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#0f0f14;--panel:#1a1a22;--panel2:#262631;--line:#2c2c38;--tx:#e8e8ee;--mut:#9a9aa8;
--danger:#ff6b6b;--dbg:#2a1717;--warn:#ffb84d;--wbg:#2a2113;--acc:#6cf08a;--abg:#16271c;--blue:#5aa9ff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.6 "Segoe UI",system-ui,sans-serif;padding:18px;}
.head{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;}
.brand{display:flex;align-items:center;gap:11px;}
.badge{width:38px;height:38px;border-radius:50%;background:var(--abg);color:var(--acc);
display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;}
.brand h1{margin:0;font-size:19px;font-weight:600;}
.brand p{margin:0;font-size:12px;color:var(--mut);}
.live{font-size:12px;color:var(--acc);display:flex;align-items:center;gap:6px;}
.dot{width:8px;height:8px;border-radius:50%;background:var(--acc);}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:12px;}
.card h2{margin:0 0 10px;font-size:12px;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.rec{border-radius:11px;padding:12px 14px;margin-bottom:10px;}
.a-danger{background:var(--dbg);border:1px solid #5a2a2a;}
.a-warn{background:var(--wbg);border:1px solid #5a4420;}
.a-info{background:var(--abg);border:1px solid #265036;}
.rtext{font-weight:600;font-size:15px;margin-bottom:5px;}
.a-danger .rtext{color:#ffc6c6;}
.a-warn .rtext{color:#ffdca0;}
.a-info .rtext{color:#c4f0d4;}
.a-buy{background:#26210f;border:1px solid #6a5a22;}
.a-buy .rtext{color:#ffe08a;}
.badge-buy{background:#caa23a;color:#1a1405;font-size:11px;font-weight:700;padding:1px 7px;border-radius:6px;margin-right:8px;letter-spacing:.03em;}
.rwhy{font-size:14px;line-height:1.55;color:var(--tx);opacity:.92;}
.rstat{margin-top:8px;padding-top:7px;border-top:1px solid rgba(255,255,255,.13);font-size:13px;color:var(--blue);}
.row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--line);font-size:14px;}
.row:last-child{border-bottom:0;}
.pill{font-size:11px;padding:2px 8px;border-radius:7px;}
.p-crit{background:var(--dbg);color:#ffb0b0;}
.p-low{background:var(--wbg);color:#ffd28a;}
.spike{color:var(--blue);}
.me{color:var(--acc);font-weight:600;}
.mate{color:var(--blue);font-weight:600;}
.tag{font-size:11px;color:var(--mut);border:1px solid var(--line);border-radius:6px;padding:1px 6px;margin-right:9px;flex:none;}
.empty{color:var(--mut);font-size:13px;}
@media(max-width:760px){.grid{grid-template-columns:1fr;}}
</style></head><body>
<div class="head">
  <div class="brand"><div class="badge">CR</div>
    <div><h1>Coach Roland</h1><p id="sub">connecting…</p></div></div>
  <div class="live"><span class="dot"></span><span id="status">live</span></div>
</div>

<div class="card"><h2>Coach says</h2>
  <div id="advice"><div class="empty">Waiting for the lobby…</div></div></div>

<div class="grid">
  <div class="card"><h2>Lobby &middot; Double Up (4 teams)</h2><div id="lobby"><div class="empty">—</div></div></div>
  <div class="card"><h2>Positioning &middot; experimental</h2>
    <div id="pos"><div class="empty">Board-read positioning coming soon.</div></div></div>
</div>

<script>
function recCard(r){
  var sev = r.severity || "info";
  var badge = sev==="buy" ? '<span class="badge-buy">IMPORTANT</span>' : '';
  var why = r.why ? '<div class="rwhy">'+r.why+'</div>' : '';
  var stat = r.stat ? '<div class="rstat">'+r.stat+'</div>' : '';
  return '<div class="rec a-'+sev+'"><div class="rtext">'+badge+r.text+'</div>'+why+stat+'</div>';
}
function render(s){
  document.getElementById("sub").textContent =
    (s.event==="game_over"?"game over — session cleared":(s.ts?("updated "+s.ts):"waiting"));
  var adv=document.getElementById("advice");
  adv.innerHTML=(s.advice&&s.advice.length)?s.advice.map(recCard).join("")
    :'<div class="empty">No new threats — hold steady.</div>';

  var lob=document.getElementById("lobby");
  var players=(s.data&&s.data.players)||[];
  lob.innerHTML=players.length?players.map(function(p){
    var tag=p.team?'<span class="tag">'+p.team+'</span>':'';
    var name=p.is_self?'<span class="me">YOU</span>'
      :(p.is_partner?'<span class="mate">'+(p.name||"partner")+' (partner)</span>':(p.name||"?"));
    var right;
    if(p.unit){right='<span class="spike">'+p.unit+" "+"★".repeat(p.stars||1)+"</span>";}
    else if(typeof p.hp==="number"&&p.hp<=20){right='<span class="pill p-crit">'+p.hp+" — about to die</span>";}
    else if(typeof p.hp==="number"&&p.hp<=40){right='<span class="pill p-low">'+p.hp+" hp</span>";}
    else{right='<span style="color:var(--mut)">'+(p.hp!=null?p.hp+" hp":"")+"</span>";}
    return '<div class="row">'+tag+'<span style="flex:1">'+name+'</span>'+right+'</div>';
  }).join(""):'<div class="empty">Not in a game.</div>';

  var pos=document.getElementById("pos");
  if(s.positioning&&s.positioning.length){pos.innerHTML=s.positioning.map(recCard).join("");}
}
async function tick(){
  try{var r=await fetch("/state");render(await r.json());
      document.getElementById("status").textContent="live";}
  catch(e){document.getElementById("status").textContent="offline";}
}
tick();setInterval(tick,2000);
</script>
</body></html>"""


if __name__ == "__main__":
    main()
