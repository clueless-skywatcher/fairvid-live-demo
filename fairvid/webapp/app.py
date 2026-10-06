"""FAIR-VID live demo: a candidate's documents/record are pre-loaded; you record
their interview; the app fuses both and returns an admission verdict with
explanations.

Run:
    python -m fairvid.webapp        # then open http://127.0.0.1:5000
"""

import os
import re
import time
from pathlib import Path

from flask import Flask, abort, request, send_from_directory, render_template_string

from ..config import DISTRACTION_KEYWORDS
from ..datagen.questions import load_questions
from . import model
from .process_video import process

_RUN_ID = re.compile(r"^\d{10,16}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")

app = Flask(__name__)
RUNS = Path("/tmp/fairvid_runs")
RUNS.mkdir(exist_ok=True)

model.init()  # train scorer + pick pre-loaded candidate

try:
    _Q = load_questions()
    QUESTIONS = [{"program": p, "q": q, "time": t} for p, qs in _Q.items() for (_i, q, t) in qs]
except Exception:
    QUESTIONS = [{"program": "General", "q": "Tell us about yourself and why you applied.", "time": 60}]

CSS = """
:root{--bg:#0f172a;--card:#1e293b;--ink:#e2e8f0;--mut:#94a3b8;--acc:#38bdf8;--ok:#22c55e;--bad:#ef4444}
*{box-sizing:border-box} body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
header{padding:18px 28px;border-bottom:1px solid #334155} header h1{margin:0;font-size:20px} header span{color:var(--mut);font-size:13px}
main{max-width:1000px;margin:0 auto;padding:24px}
.card{background:var(--card);border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:20px}
.card h2{margin:0 0 12px;font-size:16px;color:var(--acc)}
select,button{font-size:15px;border-radius:8px;border:1px solid #475569;padding:10px 14px}
select{width:100%;background:#0b1220;color:var(--ink)}
button{background:var(--acc);color:#04212e;font-weight:600;cursor:pointer;border:none}
button.stop{background:var(--bad);color:#fff} button:disabled{opacity:.5;cursor:not-allowed}
video{width:100%;border-radius:10px;background:#000;margin-top:12px}
.row{display:flex;gap:18px;flex-wrap:wrap} .row>div{flex:1;min-width:260px}
table{width:100%;border-collapse:collapse;font-size:14px} td,th{padding:6px 8px;border-bottom:1px solid #334155;text-align:left}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.badge.ok{background:rgba(34,197,94,.15);color:var(--ok)} .badge.bad{background:rgba(239,68,68,.15);color:var(--bad)}
.mut{color:var(--mut)} pre{white-space:pre-wrap;background:#0b1220;padding:12px;border-radius:8px;font-size:14px}
img.doc{width:100%;border-radius:8px;border:1px solid #334155} img.frame{max-width:100%;border-radius:10px}
.verdict{font-size:28px;font-weight:800;letter-spacing:.5px} .verdict.ok{color:var(--ok)} .verdict.bad{color:var(--bad)}
.bar{height:14px;border-radius:7px;background:#0b1220;overflow:hidden;margin:6px 0} .bar>div{height:100%}
.sb{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:13px} .sb .lab{width:190px;color:var(--mut)}
.sb .track{flex:1;height:12px;background:#0b1220;border-radius:6px;position:relative}
.sb .fill{position:absolute;top:0;height:100%;border-radius:6px}
"""

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>FAIR-VID live demo</title>
<style>{{css}}</style></head><body>
<header><h1>FAIR-VID — applicant scoring with explanations</h1>
<span>pre-loaded documents + live interview → verdict + SHAP / LIME / counterfactual</span></header>
<main>
<div class="card"><h2>1 · Record the video interview</h2>
  <select id="q">{% for item in questions %}<option data-time="{{item.time}}">{{item.program}} — {{item.q}}</option>{% endfor %}</select>
  <video id="preview" autoplay muted playsinline></video>
  <div style="margin-top:12px">
    <button id="rec">● Start recording</button>
    <button id="stop" class="stop" disabled>■ Stop &amp; analyse</button>
    <span id="state" class="mut" style="margin-left:10px"></span>
  </div>
</div>

<div class="card"><h2>2 · Reference documents — diploma &amp; marksheet (read)</h2>
<p class="mut" style="font-size:13px">Read from the candidate's documents and used as the academic reference, fused with the video interview below.</p>
<div class="row">
  <div><img class="doc" src="/candidate/diploma.png" alt="diploma"><p class="mut" style="font-size:12px;text-align:center">diploma</p></div>
  <div><img class="doc" src="/candidate/transcript.png" alt="marksheet"><p class="mut" style="font-size:12px;text-align:center">marksheet</p></div>
  <div><table>
    <tr><td>Name</td><td>{{c.name}}</td></tr>
    <tr><td>Institution</td><td>{{docs.institution}}</td></tr>
    <tr><td>Programme</td><td>{{c.study_program}}</td></tr>
    <tr><td><b>GPA (from marksheet)</b></td><td><b>{{docs.gpa}} / 4.0</b></td></tr>
    {% for g in docs.grades %}<tr><td class="mut">{{g.subject}}</td><td>{{g.grade}}</td></tr>{% endfor %}
    <tr><td>Standardised test</td><td>{{c.test_score}}</td></tr>
    <tr><td>English score</td><td>{{c.english_score}}</td></tr>
    <tr><td>Work experience</td><td>{{c.work_experience_years}} yrs</td></tr>
    <tr><td>Demographics</td><td>{{c.gender}}, {{c.region}}, age {{c.age}}</td></tr>
  </table></div>
</div></div>
<div id="results"></div>
</main>
<script>
let stream, recorder, chunks=[]; const $=s=>document.querySelector(s);
async function initCam(){ try{ stream=await navigator.mediaDevices.getUserMedia({video:{width:480,height:360},audio:true});
  $('#preview').srcObject=stream;}catch(e){ $('#state').textContent='Camera/mic blocked: '+e.message; } } initCam();
$('#rec').onclick=()=>{ chunks=[]; recorder=new MediaRecorder(stream,{mimeType:'video/webm'});
  recorder.ondataavailable=e=>chunks.push(e.data); recorder.start();
  $('#rec').disabled=true; $('#stop').disabled=false; $('#state').textContent='● recording…'; };
$('#stop').onclick=()=>{ recorder.onstop=upload; recorder.stop(); $('#stop').disabled=true;
  $('#state').textContent='⏳ analysing… (Whisper + MediaPipe + Ollama, ~30s)'; };
async function upload(){ const blob=new Blob(chunks,{type:'video/webm'}); const fd=new FormData();
  fd.append('video',blob,'interview.webm'); fd.append('question',$('#q').value);
  const r=await fetch('/process',{method:'POST',body:fd}); $('#results').innerHTML=await r.text();
  $('#rec').disabled=false; $('#state').textContent='✓ done'; window.scrollTo(0,document.body.scrollHeight); }
</script></body></html>"""

RESULTS = """
<div class="card"><h2>Verdict</h2>
<div class="verdict {{ 'ok' if v.admit else 'bad' }}">{{ 'ADMIT' if v.admit else 'DO NOT ADMIT' }}</div>
<p class="mut">admission probability: <b>{{ (v.probability*100)|round(1) }}%</b> (threshold 50%)</p>
<div class="bar"><div style="width:{{ (v.probability*100)|round(1) }}%;background:{{ '#22c55e' if v.admit else '#ef4444' }}"></div></div>
<p class="mut" style="font-size:12px">Fused from the reference documents (diploma + marksheet) and the recorded video interview.</p></div>

<div class="card"><h2>Why — feature contributions (SHAP)</h2>
{% for s in shap_bars %}
<div class="sb"><span class="lab">{{s.name}}</span>
<span class="track"><span class="fill" style="left:{{s.left}}%;width:{{s.width}}%;background:{{ '#22c55e' if s.pos else '#ef4444' }}"></span></span>
<span style="width:54px;text-align:right">{{s.value}}</span></div>
{% endfor %}
<p class="mut" style="font-size:12px">Green pushes toward admission, red pushes away; centre = neutral.</p></div>

<div class="card"><h2>Counterfactual — what would change the decision</h2>
{% if v.admit %}<p class="mut">Already above the threshold; no change needed to admit.</p>
{% elif v.counterfactual.changes_in_original_units %}
<p>To reach admission (probability {{ (v.counterfactual.start_probability*100)|round(1) }}% &rarr; {{ (v.counterfactual.final_probability*100)|round(1) }}%), change:</p>
<table>{% for k,d in v.counterfactual.changes_in_original_units.items() %}<tr><td>{{k}}</td><td>{{ '%+.2f'|format(d) }}</td></tr>{% endfor %}</table>
{% else %}<p class="mut">No small realistic change flips the decision.</p>{% endif %}</div>

<div class="card"><h2>Pipeline stages</h2>
<p class="mut" style="font-size:13px"><b>Question:</b> {{r.question}}</p>
<table><tr><th>Stage</th><th>Status</th><th>Time</th></tr>
{% for name,st in r.stages.items() %}<tr><td>{{name}}</td>
<td>{% if st.ok %}<span class="badge ok">ok</span>{% else %}<span class="badge bad">skipped</span> <span class="mut">{{st.error}}</span>{% endif %}</td>
<td class="mut">{{st.secs}}s</td></tr>{% endfor %}</table></div>

<div class="row">
<div class="card"><h2>Transcript (Whisper)</h2><pre>{{ r.transcript or "—" }}</pre></div>
<div class="card"><h2>Middle frame + description</h2>
{% if r.frame_url %}<img class="frame" src="{{r.frame_url}}">{% endif %}
{% if r.frame_description %}<p class="mut" style="margin-top:8px">backend:
<span class="badge {{'ok' if r.frame_description.backend=='ollama' else 'bad'}}">{{r.frame_description.backend}} {{r.frame_description.model}}</span></p>
{% if r.frame_description.error %}<p class="mut">{{ r.frame_description.error }}</p>{% endif %}
<pre>{{r.frame_description.text}}</pre>{% endif %}</div>
</div>

<div class="row">
<div class="card"><h2>Behaviour (MediaPipe)</h2>
{% if r.behaviour %}<table>{% for k,val in r.behaviour.items() %}<tr><td>{{k}}</td><td>{{val}}</td></tr>{% endfor %}</table>
{% else %}<p class="mut">not available</p>{% endif %}</div>
<div class="card"><h2>Grade (transcript auditor)</h2>
{% if r.grade %}<table>
<tr><td>Grader</td><td>{{ r.grade.backend }}{% if r.grade.model %} · {{ r.grade.model }}{% endif %}</td></tr>
{% if r.grade.error %}<tr><td>Model error</td><td>{{ r.grade.error }}</td></tr>{% endif %}
<tr><td>Overall</td><td><b>{{r.grade.overall_score}}/100</b></td></tr>
{% if r.grade.executive_summary %}<tr><td>Summary</td><td>{{ r.grade.executive_summary }}</td></tr>{% endif %}
<tr><td>Relevance</td><td>{{r.grade.metrics.relevance_score}}/10</td></tr>
<tr><td>Clarity</td><td>{{r.grade.metrics.clarity_score}}/10</td></tr>
<tr><td>Structure</td><td>{{r.grade.metrics.structure_score}}/10</td></tr>
<tr><td>Reads like AI script?</td><td>{% if r.grade.ai_script_detection.is_likely_reading_llm_text %}<span class="badge bad">yes</span>{% else %}<span class="badge ok">no</span>{% endif %}</td></tr>
</table>{% else %}<p class="mut">needs a transcript</p>{% endif %}</div>
</div>
"""


def _shap_bars(shap_local):
    """Centre-anchored bar geometry for signed SHAP values."""
    if not shap_local:
        return []
    mx = max(abs(v) for _, v in shap_local) or 1.0
    out = []
    for name, val in shap_local:
        w = abs(val) / mx * 48.0
        out.append({"name": name, "value": round(val, 3), "pos": val >= 0,
                    "width": round(w, 1), "left": round(50.0 if val >= 0 else 50.0 - w, 1)})
    return out


@app.route("/")
def home():
    return render_template_string(PAGE, css=CSS, questions=QUESTIONS,
                                  c=model.candidate(), docs=model.candidate_documents())


@app.route("/process", methods=["POST"])
def do_process():
    runid = str(int(time.time() * 1000))
    work = RUNS / runid
    work.mkdir(parents=True, exist_ok=True)
    video = work / "interview.webm"
    request.files["video"].save(str(video))
    question = request.form.get("question", "")
    r = process(str(video), question, str(work))
    if r.get("frame_file"):
        r["frame_url"] = f"/run/{runid}/frame.jpg"

    g = r.get("grade") or {}
    interview = {
        "overall": float(g.get("overall_score", 50)),
        "relevance": float((g.get("metrics") or {}).get("relevance_score", 5)),
        "ai_rate": 1.0 if (g.get("ai_script_detection") or {}).get("is_likely_reading_llm_text") else 0.0,
    }
    b = r.get("behaviour") or {}
    behaviour = {
        "composite": float(b.get("Composite score", 70)),
        "reading_prob": float(b.get("Reading Prob", 20)),
        "smile": float(b.get("Smile Frequency", 20)),
    }
    desc = ((r.get("frame_description") or {}).get("text") or "").lower()
    visual_distraction = 1.0 if any(k in desc for k in DISTRACTION_KEYWORDS) else 0.0

    v = model.score_live(interview, behaviour, visual_distraction)
    return render_template_string(RESULTS, r=r, v=v, shap_bars=_shap_bars(v["shap_local"]))


@app.route("/candidate/<name>")
def candidate_doc(name):
    if not _SAFE_NAME.match(name):
        abort(404)
    return send_from_directory(model.candidate_doc_dir(), name)


@app.route("/run/<runid>/<name>")
def run_file(runid, name):
    # run ids are millisecond timestamps. Reject anything else so ".." cannot
    # walk out of the run folder.
    if not _RUN_ID.match(runid) or not _SAFE_NAME.match(name):
        abort(404)
    return send_from_directory(RUNS / runid, name)


def main():
    host = os.environ.get("FAIRVID_HOST", "127.0.0.1")
    port = int(os.environ.get("FAIRVID_PORT", "5000"))
    print(f"FAIR-VID demo at http://{host}:{port}  (Ctrl-C to stop)")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
