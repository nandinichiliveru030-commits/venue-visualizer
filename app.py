import json
import datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai

st.set_page_config(page_title="Celebration & Event Planner", layout="wide")

MODEL_NAME = "gemini-3.8-flash"
ALLOWED = {"table", "chair", "stage", "light", "banner", "dance_floor"}
UNIT_COST = {"table": 1500, "chair": 150, "stage": 25000, "light": 2000,
             "banner": 1200, "dance_floor": 12000}  # INR, rough estimates

VENUE_PROMPT = """You are an event venue scene designer.
Return ONLY valid JSON (no markdown, no explanation) in this exact shape:
{
  "room": {"width": number, "length": number, "height": 4,
           "wall_color": "#hex", "floor_color": "#hex", "ambient_color": "#hex"},
  "objects": [
    {"type": "table|chair|stage|light|banner|dance_floor",
     "x": number, "z": number, "color": "#hex",
     "w": number, "d": number, "rotation": number}
  ]
}
Rules:
- Room center is (0,0). x must be within [-width/2, width/2], z within [-length/2, length/2].
- Allowed types ONLY: table, chair, stage, light, banner, dance_floor.
- Stage goes along the back wall (negative z). Banner goes on the back wall behind the stage.
- Place tables in neat rows/rings with chairs around them. No overlapping objects.
- Add 4 to 8 lights using theme colors. Keep total objects under 110.
- Colors must match the theme (neon for cyberpunk, gold/white for royal, green for jungle).
- w and d are footprint size in meters (table ~1.6, stage ~ width*0.6 by 2.5, dance_floor ~4).
"""

PLAN_PROMPT = """You are an expert event planner for events in India.
Return ONLY valid JSON (no markdown, no explanation) in this exact shape:
{
  "summary": "2 sentence overview of the plan",
  "budget": [{"category": "Venue", "percent": 30, "notes": "short tip"}],
  "timeline": [{"when": "8 weeks before", "task": "what to do"}],
  "vendors": [{"vendor": "Caterer", "ask": "what to ask or confirm", "est_cost": number}],
  "ideas": {"Theme": ["idea"], "Decor": ["idea"], "Food": ["idea"],
            "Activities": ["idea"], "Return gifts": ["idea"]}
}
Rules:
- budget has 6 to 9 categories, percents add up to 100, and one category is named "Decor & Lighting".
- timeline has 8 to 12 items in order, counting down to the event day, using the event date given.
- vendors has 6 to 10 items; est_cost is in INR and the total stays within the budget.
- ideas has 3 to 5 items per list, personalised to the event type, theme, city, guest count and special needs.
- All money is in INR.
"""


def secret_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None


def get_model(system_prompt):
    key = secret_key() or st.session_state.get("api_key")
    if not key:
        return None
    genai.configure(api_key=key)
    return genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=system_prompt,
        generation_config={"response_mime_type": "application/json", "temperature": 0.7},
    )


def call_json(system_prompt, prompt):
    model = get_model(system_prompt)
    if model is None:
        raise ValueError("Add your Gemini API key in the sidebar.")
    resp = model.generate_content(prompt)
    text = resp.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(text)


# ---------------- Venue (3D) ----------------
def validate_layout(layout):
    """Clamp everything inside room bounds and drop unknown object types."""
    room = layout.get("room", {})
    w = float(room.get("width", 10))
    l = float(room.get("length", 8))
    room.update({
        "width": w, "length": l, "height": float(room.get("height", 4)),
        "wall_color": room.get("wall_color", "#222233"),
        "floor_color": room.get("floor_color", "#111111"),
        "ambient_color": room.get("ambient_color", "#334455"),
    })
    clean = []
    for o in layout.get("objects", [])[:110]:
        if o.get("type") not in ALLOWED:
            continue
        try:
            o["x"] = max(-w / 2 + 0.3, min(w / 2 - 0.3, float(o.get("x", 0))))
            o["z"] = max(-l / 2 + 0.3, min(l / 2 - 0.3, float(o.get("z", 0))))
            o["w"] = float(o.get("w", 1.5))
            o["d"] = float(o.get("d", 1.5))
            o["rotation"] = float(o.get("rotation", 0))
        except (TypeError, ValueError):
            continue
        o["color"] = o.get("color", "#ffffff")
        clean.append(o)
    return {"room": room, "objects": clean}


def generate_layout(prompt):
    return validate_layout(call_json(VENUE_PROMPT, prompt))


def viewer_html(layout, height=560):
    data = json.dumps(layout).replace("</", "<\\/")
    return f"""
<div id="c" style="width:100%;height:{height}px;background:#000;border-radius:12px;overflow:hidden"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const L = {data};
const el = document.getElementById('c');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x05050a);
const cam = new THREE.PerspectiveCamera(60, el.clientWidth/el.clientHeight, 0.1, 200);
const R = L.room;
const span = Math.max(R.width, R.length);
cam.position.set(0, span*0.75, span*0.95);
const ren = new THREE.WebGLRenderer({{antialias:true}});
ren.setPixelRatio(window.devicePixelRatio || 1);
ren.setSize(el.clientWidth, el.clientHeight);
el.appendChild(ren.domElement);
const ctl = new THREE.OrbitControls(cam, ren.domElement);
ctl.target.set(0, 1, 0);
ctl.maxPolarAngle = Math.PI/2.05;

scene.add(new THREE.AmbientLight(new THREE.Color(R.ambient_color), 0.6));

// floor
const floor = new THREE.Mesh(new THREE.PlaneGeometry(R.width, R.length),
  new THREE.MeshStandardMaterial({{color:R.floor_color, roughness:0.6}}));
floor.rotation.x = -Math.PI/2; scene.add(floor);
// walls (back, left, right)
const wm = new THREE.MeshStandardMaterial({{color:R.wall_color, side:THREE.DoubleSide}});
const back = new THREE.Mesh(new THREE.PlaneGeometry(R.width, R.height), wm);
back.position.set(0, R.height/2, -R.length/2); scene.add(back);
const left = new THREE.Mesh(new THREE.PlaneGeometry(R.length, R.height), wm);
left.rotation.y = Math.PI/2; left.position.set(-R.width/2, R.height/2, 0); scene.add(left);
const right = left.clone(); right.position.x = R.width/2; scene.add(right);

function mat(c, glow) {{
  return new THREE.MeshStandardMaterial({{color:c, emissive: glow ? c : 0x000000,
    emissiveIntensity: glow ? 0.9 : 0, roughness:0.5}});
}}

L.objects.forEach(o => {{
  let m;
  if (o.type === 'table') {{
    m = new THREE.Mesh(new THREE.CylinderGeometry(o.w/2, o.w/2, 0.75, 24), mat(o.color));
    m.position.set(o.x, 0.375, o.z);
  }} else if (o.type === 'chair') {{
    m = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.9, 0.45), mat(o.color));
    m.position.set(o.x, 0.45, o.z);
  }} else if (o.type === 'stage') {{
    m = new THREE.Mesh(new THREE.BoxGeometry(o.w, 0.6, o.d), mat(o.color, true));
    m.position.set(o.x, 0.3, o.z);
  }} else if (o.type === 'dance_floor') {{
    m = new THREE.Mesh(new THREE.BoxGeometry(o.w, 0.05, o.d), mat(o.color, true));
    m.position.set(o.x, 0.03, o.z);
  }} else if (o.type === 'banner') {{
    m = new THREE.Mesh(new THREE.PlaneGeometry(o.w, 1.6), mat(o.color, true));
    m.position.set(o.x, 2.6, -R.length/2 + 0.05);
  }} else if (o.type === 'light') {{
    const col = new THREE.Color(o.color);
    const pl = new THREE.PointLight(col, 1.2, R.width*1.2);
    pl.position.set(o.x, R.height-0.4, o.z); scene.add(pl);
    m = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 16), mat(o.color, true));
    m.position.copy(pl.position);
  }}
  if (m) {{ m.rotation.y = (o.rotation||0) * Math.PI/180; scene.add(m); }}
}});

function fit() {{
  const w = el.clientWidth || 800, h = el.clientHeight || 560;
  cam.aspect = w/h; cam.updateProjectionMatrix();
  ren.setSize(w, h);
}}
window.addEventListener('resize', fit);
if (window.ResizeObserver) new ResizeObserver(fit).observe(el);
setTimeout(fit, 100);
(function loop(){{ requestAnimationFrame(loop); ctl.update(); ren.render(scene, cam); }})();
</script>
"""


# ---------------- Planner ----------------
def normalize_plan(plan, total_budget):
    """Make budget percents add up to 100 and compute rupee amounts."""
    rows = []
    for b in plan.get("budget", []):
        try:
            rows.append({"category": str(b.get("category", "Other")),
                         "percent": max(0.0, float(b.get("percent", 0))),
                         "notes": str(b.get("notes", ""))})
        except (TypeError, ValueError):
            continue
    total_pct = sum(r["percent"] for r in rows) or 1
    for r in rows:
        r["percent"] = round(r["percent"] * 100 / total_pct, 1)
        r["amount"] = int(round(total_budget * r["percent"] / 100))
    vendors = []
    for v in plan.get("vendors", []):
        try:
            vendors.append({"vendor": str(v.get("vendor", "Vendor")),
                            "ask": str(v.get("ask", "")),
                            "est_cost": int(float(v.get("est_cost", 0)))})
        except (TypeError, ValueError):
            continue
    ideas = plan.get("ideas", {})
    if not isinstance(ideas, dict):
        ideas = {}
    return {
        "summary": str(plan.get("summary", "")),
        "budget": rows,
        "timeline": [t for t in plan.get("timeline", []) if isinstance(t, dict)],
        "vendors": vendors,
        "ideas": {k: [str(i) for i in v] for k, v in ideas.items() if isinstance(v, list)},
    }


def event_text(ev):
    return (f"Event type: {ev['type']}\nTheme: {ev['theme']}\nDate: {ev['date']}\n"
            f"City: {ev['city']}\nGuests: {ev['guests']}\nTotal budget: INR {ev['budget']:,}\n"
            f"Special needs: {ev['needs'] or 'none'}")


def generate_plan(ev):
    return normalize_plan(call_json(PLAN_PROMPT, event_text(ev)), ev["budget"])


def plan_to_markdown(ev, plan):
    lines = [f"# {ev['type']} plan: {ev['theme']}", "",
             f"Date: {ev['date']} | City: {ev['city']} | Guests: {ev['guests']} | "
             f"Budget: INR {ev['budget']:,}", "", plan["summary"], "", "## Budget"]
    for r in plan["budget"]:
        lines.append(f"- {r['category']}: INR {r['amount']:,} ({r['percent']}%) - {r['notes']}")
    lines += ["", "## Timeline"]
    for t in plan["timeline"]:
        lines.append(f"- {t.get('when', '')}: {t.get('task', '')}")
    lines += ["", "## Vendor checklist"]
    for v in plan["vendors"]:
        lines.append(f"- [ ] {v['vendor']}: {v['ask']} (about INR {v['est_cost']:,})")
    lines += ["", "## Ideas"]
    for k, items in plan["ideas"].items():
        lines.append(f"### {k}")
        lines += [f"- {i}" for i in items]
    return "\n".join(lines)


# ---------------- UI ----------------
st.title("🎉 Celebration & Event Planner")
st.caption("Plan the budget, timeline and vendors, then walk around your venue in 3D before you book it.")

with st.sidebar:
    st.header("Settings")
    if not secret_key():
        st.session_state["api_key"] = st.text_input("Gemini API key", type="password")
    st.markdown("3D view: drag to rotate, scroll to zoom, right-drag to pan")

with st.form("event_form"):
    r1c1, r1c2, r1c3 = st.columns(3)
    etype = r1c1.selectbox("Event type", ["Wedding", "Birthday", "Community event", "Other"], index=1)
    etheme = r1c2.text_input("Theme", "Cyberpunk birthday party with neon lights")
    edate = r1c3.date_input("Event date", datetime.date.today() + datetime.timedelta(days=60))
    r2c1, r2c2, r2c3 = st.columns(3)
    ecity = r2c1.text_input("City", "Hyderabad")
    eguests = r2c2.number_input("Guests", 10, 1000, 40, step=5)
    ebudget = r2c3.number_input("Total budget (INR)", 10000, 10000000, 100000, step=5000)
    r3c1, r3c2, r3c3 = st.columns(3)
    width = r3c1.slider("Room width (m)", 6, 30, 12)
    length = r3c2.slider("Room length (m)", 6, 30, 10)
    eneeds = r3c3.text_input("Special needs", placeholder="veg only, kids, outdoor...")
    go = st.form_submit_button("✨ Generate plan and 3D venue")

if go:
    ev = {"type": etype, "theme": etheme, "date": str(edate), "city": ecity,
          "guests": int(eguests), "budget": int(ebudget), "needs": eneeds,
          "width": width, "length": length}
    st.session_state["event"] = ev
    for k in list(st.session_state.keys()):
        if k.startswith("v_"):
            del st.session_state[k]
    with st.spinner("Building your plan..."):
        try:
            st.session_state["plan"] = generate_plan(ev)
        except Exception as e:
            st.session_state.pop("plan", None)
            st.error(f"Could not generate the plan: {e}")
    with st.spinner("Designing your venue..."):
        try:
            vprompt = (f"Theme: {ev['theme']}\nRoom: {width}m wide (x) by {length}m long (z).\n"
                       f"Guests: {ev['guests']}. Seat everyone at round tables of 6-8 with chairs.")
            st.session_state["layout"] = generate_layout(vprompt)
        except Exception as e:
            st.session_state.pop("layout", None)
            st.error(f"Could not generate the venue: {e}")

ev = st.session_state.get("event")
plan = st.session_state.get("plan")
layout = st.session_state.get("layout")

tab_plan, tab_venue = st.tabs(["📋 Plan", "🎪 3D Venue"])

with tab_plan:
    if not plan:
        st.info("Fill the form above and click Generate to see your plan.")
    else:
        st.markdown(plan["summary"])

        st.subheader("💰 Budget breakdown")
        df = pd.DataFrame([{"Category": r["category"], "Percent": r["percent"],
                            "Amount (₹)": r["amount"], "Tip": r["notes"]} for r in plan["budget"]])
        c1, c2 = st.columns([3, 2])
        c1.dataframe(df, hide_index=True, use_container_width=True)
        c2.bar_chart(df.set_index("Category")["Amount (₹)"])
        st.metric("Total budget", f"₹{ev['budget']:,}")

        st.subheader("🗓️ Timeline")
        for t in plan["timeline"]:
            st.markdown(f"**{t.get('when', '')}**: {t.get('task', '')}")

        st.subheader("✅ Vendor checklist")
        done = 0
        for i, v in enumerate(plan["vendors"]):
            label = f"**{v['vendor']}**: {v['ask']} (about ₹{v['est_cost']:,})"
            if st.checkbox(label, key=f"v_{i}"):
                done += 1
        if plan["vendors"]:
            st.progress(done / len(plan["vendors"]), text=f"{done} of {len(plan['vendors'])} vendors confirmed")

        st.subheader("💡 Personalised ideas")
        for k, items in plan["ideas"].items():
            with st.expander(k):
                for item in items:
                    st.write(f"- {item}")

        st.download_button("⬇️ Download plan (Markdown)", plan_to_markdown(ev, plan),
                           file_name="event_plan.md")

        st.divider()
        ptweak = st.text_input("Change the plan", placeholder="Make it cheaper / add a photographer / more kids activities",
                               key="plan_tweak")
        if st.button("Update plan") and ptweak:
            with st.spinner("Updating plan..."):
                try:
                    p = (f"{event_text(ev)}\nCurrent plan JSON: {json.dumps(plan)}\n"
                         f"Apply this change and return the full updated JSON: {ptweak}")
                    st.session_state["plan"] = normalize_plan(call_json(PLAN_PROMPT, p), ev["budget"])
                    for k in list(st.session_state.keys()):
                        if k.startswith("v_"):
                            del st.session_state[k]
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not update the plan: {e}")

with tab_venue:
    if not layout:
        st.info("Fill the form above and click Generate to see your 3D venue.")
    else:
        left, right = st.columns([3, 1])
        with left:
            components.html(viewer_html(layout), height=580)
        with right:
            counts = {}
            for o in layout["objects"]:
                counts[o["type"]] = counts.get(o["type"], 0) + 1
            st.subheader("Items")
            total = 0
            for t, n in counts.items():
                cost = n * UNIT_COST[t]
                total += cost
                st.write(f"**{t.replace('_', ' ').title()}** x {n}: ₹{cost:,}")
            st.metric("Rough decor estimate", f"₹{total:,}")
            if plan:
                decor = [r for r in plan["budget"] if "decor" in r["category"].lower()]
                if decor:
                    st.metric("Decor budget in your plan", f"₹{decor[0]['amount']:,}",
                              delta=f"₹{decor[0]['amount'] - total:,} left",
                              delta_color="normal")
            st.caption("Item costs are placeholder unit prices. Edit UNIT_COST in the code.")

        st.divider()
        tweak = st.text_input("Change the venue", placeholder="Move the stage to the left / add more tables / make lights purple",
                              key="venue_tweak")
        if st.button("Update layout") and tweak:
            prompt = (f"Theme: {ev['theme']}\n"
                      f"Current layout JSON: {json.dumps(layout)}\n"
                      f"Apply this change and return the full updated JSON: {tweak}")
            with st.spinner("Updating..."):
                try:
                    st.session_state["layout"] = generate_layout(prompt)
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not update: {e}")
