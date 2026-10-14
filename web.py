"""
Flask-webside til overvågning og styring af FUT-teleskopet.
"""
from flask import Flask, jsonify, render_template_string, request
import state

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="da">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FUT Telescope</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f4f6fa; --card: #fff; --text: #1a1f2e; --muted: #6b7280;
      --border: #e2e5ee; --accent: #0f766e; --danger: #dc2626;
      --shadow: 0 1px 3px rgba(0,0,0,.08);
    }
    @media(prefers-color-scheme:dark){
      :root {
        --bg: #0f1219; --card: #181d2a; --text: #f0f2f5; --muted: #8b95a5;
        --border: #272e3f; --shadow: 0 1px 3px rgba(0,0,0,.3);
      }
    }
    *{box-sizing:border-box; margin:0}
    body{font-family:system-ui,sans-serif; background:var(--bg); color:var(--text); min-height:100vh}
    .wrap{max-width:680px; margin:0 auto; padding:24px 16px}
    header{display:flex; justify-content:space-between; align-items:center; margin-bottom:20px}
    h1{font-size:1.5rem; font-weight:700}
    .pill{display:inline-block; padding:4px 12px; border-radius:20px; font-size:.8rem; font-weight:600; text-transform:uppercase}
    .pill.idle{background:#dcfce7; color:#166534}
    .pill.moving{background:#dbeafe; color:#1e40af}
    .pill.error{background:#fee2e2; color:#991b1b}
    .pill.restarting,.pill.starting,.pill.manual_pending{background:#fef3c7; color:#92400e}
    @media(prefers-color-scheme:dark){
      .pill.idle{background:#14532d; color:#86efac}
      .pill.moving{background:#1e3a5f; color:#93c5fd}
      .pill.error{background:#450a0a; color:#fca5a5}
      .pill.restarting,.pill.starting,.pill.manual_pending{background:#451a03; color:#fde68a}
    }
    .card{background:var(--card); border:1px solid var(--border); border-radius:10px; box-shadow:var(--shadow); padding:16px; margin-bottom:14px}
    .card h2{font-size:.85rem; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; margin-bottom:12px}
    .row{display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--border); font-size:.95rem}
    .row:last-child{border-bottom:none}
    .row .label{color:var(--muted)}
    .row .value{font-weight:600; font-variant-numeric:tabular-nums}
    .grid2{display:grid; grid-template-columns:1fr 1fr; gap:10px}
    .big-metric{text-align:center; padding:14px 8px; border:1px solid var(--border); border-radius:8px}
    .big-metric .label{font-size:.8rem; color:var(--muted); margin-bottom:4px}
    .big-metric .value{font-size:1.6rem; font-weight:700; font-variant-numeric:tabular-nums}
    .big-metric .sub{font-size:.75rem; color:var(--muted); margin-top:2px; font-variant-numeric:tabular-nums}
    .error-bar{background:#fef2f2; border:1px solid #fecaca; color:#991b1b; border-radius:8px; padding:10px 14px; font-size:.9rem; margin-bottom:14px}
    @media(prefers-color-scheme:dark){.error-bar{background:#300a0a; border-color:#5c1010; color:#fca5a5}}
    .note{font-size:.8rem; color:var(--muted); margin-top:4px; line-height:1.4}
    label{display:block; font-size:.85rem; color:var(--muted); margin-bottom:4px}
    input{width:100%; height:38px; border:1px solid var(--border); border-radius:6px; padding:0 10px; background:transparent; color:var(--text); font:inherit}
    .form-grid{display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px}
    button{height:38px; border:none; border-radius:6px; padding:0 18px; font:inherit; font-weight:600; cursor:pointer}
    .btn-primary{background:var(--accent); color:#fff}
    .btn-danger{background:var(--danger); color:#fff}
    button:disabled{opacity:.5; cursor:not-allowed}
    .actions{display:flex; gap:10px; margin-top:10px}
    .switch-row{display:flex; justify-content:space-between; align-items:center; gap:12px; margin-top:14px}
    .switch-row label{margin:0}
    .switch{width:44px; height:24px; appearance:none; background:var(--border); border-radius:999px; cursor:pointer; position:relative}
    .switch:before{content:""; position:absolute; width:18px; height:18px; left:3px; top:3px; border-radius:50%; background:#fff; transition:transform .15s}
    .switch:checked{background:var(--accent)}
    .switch:checked:before{transform:translateX(20px)}
    .meta{font-size:.8rem; color:var(--muted); text-align:center; margin-top:18px}
  </style>
</head>
<body>
<div class="wrap">

  <header>
    <h1>🔭 FUT Telescope</h1>
    <div id="status-pill"><span class="pill starting">starting</span></div>
  </header>

  <div id="error-bar" class="error-bar" style="display:none"></div>

  <!-- Current position -->
  <div class="card">
    <h2>Current Position</h2>
    <div class="grid2">
      <div class="big-metric"><div class="label">Altitude</div><div class="value" id="cur_alt">–</div></div>
      <div class="big-metric">
        <div class="label">Azimuth</div>
        <div class="value" id="cur_az">–</div>
        <div class="sub">compass: <span id="cur_az_compass">–</span></div>
      </div>
    </div>
    <p class="note">Az shown as ±180° from start (cable-safe) and as 0–360° compass bearing.</p>
  </div>

  <!-- Target -->
  <div class="card">
    <h2>Target</h2>
    <div class="grid2" style="margin-bottom:8px">
      <div class="big-metric"><div class="label">Target Alt</div><div class="value" id="tgt_alt">–</div></div>
      <div class="big-metric">
        <div class="label">Target Az</div>
        <div class="value" id="tgt_az">–</div>
        <div class="sub">compass: <span id="tgt_az_compass">–</span></div>
      </div>
    </div>
    <div class="row"><span class="label">Source</span><span class="value" id="tgt_src">–</span></div>
    <div class="row"><span class="label">API RA</span><span class="value" id="api_ra">–</span></div>
    <div class="row"><span class="label">API Dec</span><span class="value" id="api_dec">–</span></div>
  </div>

  <!-- Last move -->
  <div class="card">
    <h2>Last Movement</h2>
    <div class="row"><span class="label">Az moved</span><span class="value" id="mv_az">–</span></div>
    <div class="row"><span class="label">Alt moved</span><span class="value" id="mv_alt">–</span></div>
    <div class="row"><span class="label">Time</span><span class="value" id="mv_time">–</span></div>
  </div>

  <!-- Controls -->
  <div class="card">
    <h2>Manual Target</h2>
    <form id="manual-form">
      <div class="form-grid">
        <div><label>Altitude (0–90°)</label><input id="m-alt" type="number" step="0.01" min="0" max="90" required></div>
        <div><label>Azimuth (0–360°)</label><input id="m-az" type="number" step="0.01" min="0" max="360" required></div>
      </div>
      <button class="btn-primary" type="submit" style="width:100%">Send target</button>
    </form>
    <p class="note">If the shortest path would exceed the ±180° cable limit, the long way is used automatically.</p>
    <div class="switch-row">
      <label for="api-connected">Listen to API positions</label>
      <input class="switch" id="api-connected" type="checkbox" checked>
    </div>
    <p class="note">Turn this off to control the telescope manually without accepting new API positions.</p>
  </div>

  <div class="actions">
    <button class="btn-danger" id="restart-btn" onclick="restart()" style="flex:1">Restart telescope</button>
  </div>

  <div class="meta">
    Last update: <span id="last_upd">–</span>
  </div>

</div>
<script>
function fmt(v, u) { return v != null ? parseFloat(v).toFixed(4) + u : "–"; }
function compassAz(v) {
  // Konverter fysisk Az (-180..+180) til kompas-bæring (0..360).
  if (v == null) return "–";
  const c = ((parseFloat(v) % 360) + 360) % 360;
  return c.toFixed(4) + "°";
}
function fmtTime(epoch) {
  if (!epoch) return "–";
  const d = new Date(epoch * 1000);
  return d.toLocaleTimeString("da-DK", {hour:"2-digit",minute:"2-digit",second:"2-digit"});
}
async function refresh() {
  try {
    const s = (await (await fetch("/api/status")).json());
    document.getElementById("cur_alt").textContent = fmt(s.current_alt, "°");
    document.getElementById("cur_az").textContent  = fmt(s.current_az, "°");
    document.getElementById("cur_az_compass").textContent = compassAz(s.current_az);
    document.getElementById("tgt_alt").textContent = fmt(s.target_alt, "°");
    document.getElementById("tgt_az").textContent  = fmt(s.target_az, "°");
    document.getElementById("tgt_az_compass").textContent = compassAz(s.target_az);
    document.getElementById("tgt_src").textContent = s.target_source || "–";
    document.getElementById("api_ra").textContent  = fmt(s.api_ra, "°");
    document.getElementById("api_dec").textContent = fmt(s.api_dec, "°");
    document.getElementById("api-connected").checked = !!s.api_connected;
    document.getElementById("mv_az").textContent   = fmt(s.last_motor_az_deg, "°");
    document.getElementById("mv_alt").textContent  = fmt(s.last_motor_alt_deg, "°");
    document.getElementById("mv_time").textContent = fmtTime(s.last_move);
    document.getElementById("last_upd").textContent= fmtTime(s.last_update);
    const bar = document.getElementById("error-bar");
    if (s.last_error) { bar.textContent = s.last_error; bar.style.display = "block"; }
    else { bar.style.display = "none"; }
    const cls = s.status || "starting";
    document.getElementById("status-pill").innerHTML =
      '<span class="pill '+cls+'">'+cls+(s.restart_pending?" (pending)":"")+'</span>';
    document.getElementById("restart-btn").disabled = !!s.restart_pending;
  } catch(e) { console.error(e); }
}
async function postJson(url, body) {
  const r = await fetch(url, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const j = await r.json(); if(!r.ok) throw new Error(j.error||"Failed"); return j;
}
document.getElementById("manual-form").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await postJson("/api/manual-target", {
      alt: Number(document.getElementById("m-alt").value),
      az:  Number(document.getElementById("m-az").value)
    });
    refresh();
  } catch(e) { alert(e.message); }
});
document.getElementById("api-connected").addEventListener("change", async e => {
  try {
    await postJson("/api/api-connection", {connected: e.target.checked});
    refresh();
  } catch (error) {
    e.target.checked = !e.target.checked;
    alert(error.message);
  }
});
async function restart() {
  if (!confirm("Restart the telescope? Position will be reset to 0/0.")) return;
  document.getElementById("restart-btn").disabled = true;
  await fetch("/api/restart",{method:"POST"});
  refresh();
}
refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/api/status")
def api_status():
    return jsonify(state.get_state())


@app.route("/api/manual-target", methods=["POST"])
def api_manual_target():
    data = request.get_json(silent=True) or {}
    try:
        state.request_manual_target(data["alt"], data["az"])
    except KeyError as e:
        return jsonify({"error": f"{e.args[0]} is required."}), 400
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


@app.route("/api/restart", methods=["POST"])
def api_restart():
    state.request_restart()
    return jsonify({"ok": True})


@app.route("/api/api-connection", methods=["POST"])
def api_connection():
    data = request.get_json(silent=True) or {}
    connected = data.get("connected")
    if not isinstance(connected, bool):
        return jsonify({"error": "connected must be true or false."}), 400
    state.set_api_connected(connected)
    return jsonify({"ok": True, "api_connected": connected})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
