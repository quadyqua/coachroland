"""Coach Roland dashboard — a nice local web UI for your second monitor.

Runs a tiny local web server. Open it in a browser, drag to monitor 2, fullscreen.
The watcher runs in the background and pushes live reads; the page polls /state and
re-renders. Every recommendation has a hover tooltip explaining WHY (+ a stat slot).

    python -m tftwatch.dashboard                     # live (watcher in background; needs game on screen)
    python -m tftwatch.dashboard --comp dark_star_jhin   # live + contest-aware comp advice
    python -m tftwatch.dashboard --demo              # static sample data, no game/API — preview the UI
"""
import argparse
import threading

from flask import Flask, jsonify, Response
from dotenv import load_dotenv

from . import compguide
# NOTE: `.watcher` is imported lazily inside main() (live mode only) so that
# `--demo` can preview the UI without the screen-capture/vision deps installed.

load_dotenv()

STATE = {"ts": None, "event": "idle", "data": None, "advice": [], "positioning": [], "comp": None,
         "shop": [], "econ": None, "items": [], "bench": [], "stage": None, "gold": None, "level": None}

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
         "priority": 100, "timer": 30,
         "why": "Active pick — choose one of the 3 now. Best of the three for a fast-9 board — econ "
                "now compounds into hitting Jhin at 8. Rule: an emblem that points your comp > a "
                "proven augment > econ early, combat later.",
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
    "gold": 3, "level": 6, "stage": "4-2",
    "shop": [
        {"name": "Kai'Sa", "cost": 2, "action": "buy", "carry": False},
        {"name": "Cho'Gath", "cost": 1, "action": "buy", "carry": False},
        {"name": "Karma", "cost": 3, "action": "buy", "carry": False},
        {"name": "Samira", "cost": 1, "action": "give", "carry": False, "for": "partner", "partner": "Wisp"},
        {"name": "Jhin", "cost": 5, "action": "lock", "carry": True},
    ],
    "econ": {"text": "Save and build econ", "severity": "info",
             "why": "Fast-9 board at 3 gold — hold toward 50 for interest, play your strongest board, "
                    "and slam item pieces. Roll at level 8."},
    "items": [
        {"name": "B.F. Sword", "take": True, "carry": "Jhin"},
        {"name": "Tear of the Goddess", "take": False, "carry": "Jhin"},
        {"name": "Recurve Bow", "take": True, "carry": "Jhin"},
    ],
    "bench": [
        {"name": "Talon", "cost": 1, "stars": 1, "slot": 0},
        {"name": "Talon", "cost": 1, "stars": 1, "slot": 1},
        {"name": "Caitlyn", "cost": 1, "stars": 2, "slot": 2},
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


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tftwatch.dashboard", description="Coach Roland dashboard")
    p.add_argument("--demo", action="store_true", help="static sample data, no game/API")
    p.add_argument("--brain", action="store_true",
                   help="one live brain call on a sample state -> real generated coaching in the UI")
    p.add_argument("--comp", metavar="KEY|CARRY",
                   help="your line (compguide key or carry name) -> contest-aware advice")
    p.add_argument("--partner", metavar="NAME", help="Double Up partner's name")
    p.add_argument("--partner-comp", metavar="KEY|CARRY", help="partner's line")
    p.add_argument("--board", action="store_true", help="also read your board for positioning (PAID gpt-4o — positioning isn't free yet)")
    p.add_argument("--augments", action="store_true", help="also read your augment choices (free, local icon match)")
    p.add_argument("--shop", action="store_true", help="also read your shop/gold/level -> 'buy this' advice (free, local)")
    p.add_argument("--items", action="store_true", help="read the item-choice screen -> highlight carry items (free, local)")
    p.add_argument("--offers", action="store_true", help="read the God-choice screen -> which God to take (free, local OCR)")
    p.add_argument("--rules-only", action="store_true", help="(deprecated — the free rules coach is the default now)")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if args.brain:
        from . import brain
        STATE.update(_SAMPLE)               # keep the sample lobby/positioning for context
        STATE["comp"] = compguide.comp_detail("dark_star_jhin")
        try:
            out = brain.advise(brain._DEMO_STATE)
            STATE["advice"] = out["recs"]
            STATE["comp"] = compguide.comp_detail(out.get("comp_key")) or STATE["comp"]
            STATE["ts"] = "brain"
            print(f"Brain demo — live coaching from {brain.DEFAULT_MODEL}. "
                  "Open http://127.0.0.1:8765")
        except Exception as e:
            print(f"Brain call failed ({e}); showing static sample instead.")
    elif args.demo:
        STATE.update(_SAMPLE)
        STATE["comp"] = compguide.comp_detail("dark_star_jhin")
        print("Demo mode — open http://127.0.0.1:8765  (sample data, no game/API)")
    else:
        from .watcher import watch
        threading.Thread(
            target=lambda: watch(on_update=_on_update, comp_key=args.comp,
                                 partner_name=args.partner, partner_comp_key=args.partner_comp,
                                 board=args.board, augments=args.augments, shop=args.shop,
                                 items=args.items, offers=args.offers, use_brain=False),  # live dashboard = free rules coach
            daemon=True).start()
        print("Live — open http://127.0.0.1:8765  (drag to monitor 2, fullscreen). Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=8765, debug=False)


INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Coach Roland</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#1c1d21;--panel:#23242a;--panel2:#2b2c33;--line:#37383f;--tx:#f1e3e4;--mut:#ccbcbc;
--danger:#cf8d92;--dbg:#2e2428;--warn:#a288a6;--wbg:#2a2430;--acc:#a288a6;--abg:#26262d;--blue:#bb9bb0;}
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
.a-danger{background:var(--dbg);border:1px solid #5a3a3e;}
.a-warn{background:var(--wbg);border:1px solid #4e4152;}
.a-info{background:var(--abg);border:1px solid #3a3a44;}
.rtext{font-weight:600;font-size:15px;margin-bottom:5px;}
.a-danger .rtext{color:#e8b6ba;}
.a-warn .rtext{color:#d8bcd6;}
.a-info .rtext{color:#d6cccd;}
.a-buy{background:#2a2430;border:1px solid #5e4a62;}
.a-buy .rtext{color:#d9bcd9;}
.badge-buy{background:#a288a6;color:#1c1d21;font-size:11px;font-weight:700;padding:1px 7px;border-radius:6px;margin-right:8px;letter-spacing:.03em;}
/* Active, time-boxed choice (2 Gods / 3 augments) — pinned to top, loud, pulsing. */
.a-choice{background:#2a2430;border:2px solid var(--warn);
  box-shadow:0 0 0 1px var(--warn),0 0 18px rgba(162,136,166,.35);animation:pulse 1.3s ease-in-out infinite;}
.a-choice .rtext{color:#e7d0e7;font-size:17px;}
@keyframes pulse{0%,100%{box-shadow:0 0 0 1px var(--warn),0 0 8px rgba(162,136,166,.20);}
  50%{box-shadow:0 0 0 1px var(--warn),0 0 24px rgba(162,136,166,.6);}}
.badge-choice{background:var(--warn);color:#1c1d21;font-size:11px;font-weight:800;padding:2px 8px;
  border-radius:6px;margin-right:8px;letter-spacing:.04em;}
.timer{color:var(--warn);font-weight:800;}
.rwhy{font-size:14px;line-height:1.55;color:var(--tx);opacity:.92;}
.rstat{margin-top:8px;padding-top:7px;border-top:1px solid rgba(255,255,255,.13);font-size:13px;color:var(--blue);}
.row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--line);font-size:14px;}
.row:last-child{border-bottom:0;}
.pill{font-size:11px;padding:2px 8px;border-radius:7px;}
.p-crit{background:var(--dbg);color:#e8b0b4;}
.p-low{background:var(--wbg);color:#d8bcd6;}
.spike{color:var(--blue);}
.me{color:var(--acc);font-weight:600;}
.mate{color:var(--blue);font-weight:600;}
.tag{font-size:11px;color:var(--mut);border:1px solid var(--line);border-radius:6px;padding:1px 6px;margin-right:9px;flex:none;}
.empty{color:var(--mut);font-size:13px;}
/* Your Comp panel — the "what am I building" board. */
.compcard{background:#23242a;border:1px solid #3a3a44;}
.compname{font-size:22px;font-weight:700;color:#e7d6e7;}
.compname .ps{font-size:12px;font-weight:600;color:var(--mut);margin-left:8px;text-transform:uppercase;letter-spacing:.05em;}
.compsub{font-size:13px;color:var(--mut);margin:3px 0 11px;}
.compsub b{color:var(--tx);}
.steplbl{font-size:11px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin:11px 0 6px;}
.approx{color:var(--warn);text-transform:none;letter-spacing:0;font-weight:500;font-size:11px;}
.board{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:10px;}
.unit{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:5px 10px;font-size:13px;color:var(--tx);}
.unit.carry{background:#2a2430;border-color:var(--warn);color:#d9bcd9;font-weight:700;}
.items{font-size:13px;color:var(--blue);margin-bottom:8px;}
.plan{font-size:13px;color:var(--tx);opacity:.9;border-top:1px solid var(--line);padding-top:8px;}
/* Shop strip — buy-worthy slots lit up, can't-afford slots flagged to LOCK, rest dim. */
.shop{display:grid;grid-template-columns:repeat(5,1fr);gap:7px;}
.slot{background:#1f2026;border:1px solid var(--line);border-radius:9px;padding:9px 6px;text-align:center;}
.slot .sn{font-size:13px;color:var(--tx);}
.slot .sc{font-size:11px;color:var(--mut);margin-top:2px;}
.slot.dim{opacity:.45;}
.slot.buy{background:#2a2430;border:2px solid var(--acc);}
.slot.buy .sn{color:#d9bcd9;font-weight:700;}
.slot.buy .sc{color:#a288a6;}
.slot.lock{background:#26262a;border:2px solid var(--mut);}
.slot.lock .sn{color:#e6dcdc;font-weight:700;}
.slot.lock .sc{color:#ccbcbc;}
.slot.give{background:#2c2731;border:2px solid var(--blue);}
.slot.give .sn{color:#d8bcd6;font-weight:700;}
.slot.give .sc{color:#bb9bb0;}
.shopmeta{color:var(--mut);text-transform:none;letter-spacing:0;font-weight:500;}
.econ{margin-top:11px;background:#26262d;border:1px solid #3a3a44;border-radius:10px;padding:10px 12px;font-size:13px;}
.econ b{color:#d8bcd6;}
@media(max-width:760px){.grid{grid-template-columns:1fr;}}
</style></head><body>
<div class="head">
  <div class="brand"><div class="badge">CR</div>
    <div><h1>Coach Roland</h1><p id="sub">connecting…</p></div></div>
  <div class="live"><span class="dot"></span><span id="status">live</span></div>
</div>

<div class="card compcard"><h2>Your comp · what you're building</h2>
  <div id="comp"><div class="empty">No comp locked yet — Coach Roland will commit to one.</div></div></div>

<div class="card"><h2>Your shop <span id="shopmeta" class="shopmeta"></span></h2>
  <div id="shop" class="shop"><div class="empty">No shop read — run with --shop.</div></div>
  <div id="econ"></div></div>

<div class="card" id="benchcard" style="display:none"><h2>Your bench <span class="shopmeta">&middot; recognized by portrait</span></h2>
  <div id="bench" class="shop"></div></div>

<div class="card" id="itemcard" style="display:none"><h2>Items offered &middot; take for your carry</h2>
  <div id="items" class="shop"></div></div>

<div class="card"><h2>Coach says</h2>
  <div id="advice"><div class="empty">Waiting for the lobby…</div></div></div>

<div class="grid">
  <div class="card"><h2>Lobby &middot; Double Up (4 teams)</h2><div id="lobby"><div class="empty">—</div></div></div>
  <div class="card"><h2>Positioning &middot; experimental</h2>
    <div id="pos"><div class="empty">Board-read positioning coming soon.</div></div></div>
</div>

<script>
// Deadlines for time-boxed choices live here so the countdown keeps ticking across
// the 2s state re-renders (each card's clock starts when we first see it).
var deadlines={};
function timerSpan(key,secs){
  if(!(key in deadlines)){deadlines[key]=Date.now()+(secs||30)*1000;}
  var rem=Math.max(0,Math.ceil((deadlines[key]-Date.now())/1000));
  return '<span class="timer" data-key="'+encodeURIComponent(key)+'" data-secs="'+(secs||30)+'">'
    +(rem>0?'~'+rem+'s':'now!')+'</span>';
}
function tickTimers(){
  document.querySelectorAll('.timer').forEach(function(el){
    var key=decodeURIComponent(el.getAttribute('data-key'));
    if(!(key in deadlines)){deadlines[key]=Date.now()+(parseInt(el.getAttribute('data-secs'))||30)*1000;}
    var rem=Math.max(0,Math.ceil((deadlines[key]-Date.now())/1000));
    el.textContent=rem>0?'~'+rem+'s':'now!';
  });
}
setInterval(tickTimers,1000);

function recCard(r){
  var sev = r.severity || "info";
  var urgent = (r.priority||0) >= 100;
  var cls = urgent ? "rec a-choice" : "rec a-"+sev;
  var badge;
  if(urgent){ badge='<span class="badge-choice">⏳ DECIDE NOW</span> '
                    +(r.timer?timerSpan(r.text,r.timer)+' ':''); }
  else { badge = sev==="buy" ? '<span class="badge-buy">IMPORTANT</span>' : ''; }
  var why = r.why ? '<div class="rwhy">'+r.why+'</div>' : '';
  var stat = r.stat ? '<div class="rstat">'+r.stat+'</div>' : '';
  return '<div class="'+cls+'"><div class="rtext">'+badge+r.text+'</div>'+why+stat+'</div>';
}
function unitChips(list,carry){
  return (list||[]).map(function(u){
    var c=(carry && u.toLowerCase()===carry.toLowerCase());
    return '<span class="unit'+(c?' carry':'')+'">'+u+(c?' ★':'')+'</span>';
  }).join('');
}
function renderComp(c){
  if(!c){return '<div class="empty">No comp locked yet — Coach Roland will commit to one.</div>';}
  var ps=c.playstyle?'<span class="ps">'+c.playstyle+'</span>':'';
  var early=(c.early_units&&c.early_units.length)
    ?'<div class="steplbl">① Buy now · early game</div><div class="board">'+unitChips(c.early_units,c.carry)+'</div>':'';
  var fin=(c.board&&c.board.length)
    ?'<div class="steplbl">② Final board · level 8-9 <span class="approx">(target — a guide, not gospel)</span></div><div class="board">'+unitChips(c.board,c.carry)+'</div>':'';
  var items=(c.carry_items&&c.carry_items.length)
    ?'<div class="items">'+c.carry+"'s items: "+c.carry_items.join(' + ')+'</div>':'';
  var plan=c.level_plan?'<div class="plan"><b>How to get there:</b> '+c.level_plan+'</div>':'';
  return '<div class="compname">'+c.name+ps+'</div>'+early+fin+items+plan;
}
function renderShop(s){
  var slots=s.shop||[];
  document.getElementById("shopmeta").textContent=
    (s.stage?'· stage '+s.stage+'  ':'')+(s.gold!=null?'· '+s.gold+'g':'')+(s.level!=null?'  · lvl '+s.level:'');
  document.getElementById("shop").innerHTML = slots.length ? slots.map(function(sl){
    var cls=sl.action==='buy'?'slot buy':(sl.action==='lock'?'slot lock':(sl.action==='give'?'slot give':'slot dim'));
    var tag=sl.action==='buy'?(sl.tostar?' · '+sl.tostar:' · buy')
      :(sl.action==='lock'?' · LOCK':(sl.action==='give'?' · → '+(sl.partner||'mate'):''));
    return '<div class="'+cls+'"><div class="sn">'+(sl.name||'—')+(sl.carry?' ★':'')+
      '</div><div class="sc">'+(sl.cost!=null?sl.cost+'g':'')+tag+'</div></div>';
  }).join('') : '<div class="empty" style="grid-column:1/-1">No shop read — run with --shop.</div>';
  document.getElementById("econ").innerHTML = s.econ
    ? '<div class="econ"><b>'+s.econ.text+'</b> — <span style="color:var(--mut)">'+(s.econ.why||'')+'</span></div>' : '';
}
function renderBench(s){
  var bn=s.bench||[];
  var card=document.getElementById("benchcard");
  if(card){ card.style.display = bn.length ? '' : 'none'; }
  if(!bn.length) return;
  var ones={}; bn.forEach(function(b){ if((b.stars||1)<2) ones[b.name]=(ones[b.name]||0)+1; });
  document.getElementById("bench").innerHTML = bn.map(function(b){
    var n=ones[b.name]||0, prog=(b.stars||1)<2 && n>=2;   // collecting toward a 2-star
    var stars = b.stars?(' '+Array(b.stars+1).join('★')):'';
    var lbl = prog ? (n>=3?' &middot; makes 2★':' &middot; '+n+'/3 to 2★') : '';
    return '<div class="'+(prog?'slot buy':'slot')+'"><div class="sn">'+(b.name||'?')+stars+'</div><div class="sc">'
      +(b.cost?b.cost+'g':'')+lbl+'</div></div>';
  }).join('');
}
function renderItems(s){
  var its=s.items||[];
  var card=document.getElementById("itemcard");
  if(card){ card.style.display = its.length ? '' : 'none'; }
  if(!its.length) return;
  document.getElementById("items").innerHTML = its.map(function(it){
    var cls = it.take ? 'slot buy' : 'slot dim';
    return '<div class="'+cls+'"><div class="sn">'+(it.name||'?')+'</div><div class="sc">'
      +(it.take?('take · '+(it.carry||'carry')):'skip')+'</div></div>';
  }).join('');
}
function render(s){
  if(s.event==="game_over"){ deadlines={}; }   // clear stale clocks between games
  document.getElementById("comp").innerHTML=renderComp(s.comp);
  renderShop(s);
  renderBench(s);
  renderItems(s);
  document.getElementById("sub").textContent =
    (s.event==="game_over"?"game over — session cleared":(s.ts?("updated "+s.ts):"waiting"));
  var adv=document.getElementById("advice");
  // time-boxed choices pinned to the top; everything else keeps its order.
  var advice=(s.advice||[]).slice().sort(function(a,b){return (b.priority||0)-(a.priority||0);});
  adv.innerHTML=advice.length?advice.map(recCard).join("")
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
