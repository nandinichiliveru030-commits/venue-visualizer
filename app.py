import json
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai

st.set_page_config(page_title="Virtual Twin Venue Visualizer", layout="wide")

MODEL_NAME = "gemini-3.8-flash"
ALLOWED = {"table", "chair", "stage", "light", "banner", "dance_floor"}
UNIT_COST = {"table": 1500, "chair": 150, "stage": 25000, "light": 2000,
             "banner": 1200, "dance_floor": 12000}  # INR, rough estimates

SYSTEM_PROMPT = """You are an event venue scene designer.
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


def secret_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None


def get_model():
    key = secret_key() or st.session_state.get("api_key")
    if not key:
        return None
    genai.configure(api_key=key)
    return genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=SYSTEM_PROMPT,
        generation_config={"response_mime_type": "application/json", "temperature": 0.7},
    )


def validate(layout):
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


def generate(prompt):
    model = get_model()
    if model is None:
        raise ValueError("Add your Gemini API key in the sidebar.")
    resp = model.generate_content(prompt)
    text = resp.text.strip().replace("```json", "").replace("```", "").strip()
    return validate(json.loads(text))


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
cam.position.set(0, R.height*1.6, R.length*0.95);
const ren = new THREE.WebGLRenderer({{antialias:true}});
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

window.addEventListener('resize', () => {{
  cam.aspect = el.clientWidth/el.clientHeight; cam.updateProjectionMatrix();
  ren.setSize(el.clientWidth, el.clientHeight);
}});
(function loop(){{ requestAnimationFrame(loop); ctl.update(); ren.render(scene, cam); }})();
</script>
"""


# ---------------- UI ----------------
st.title("🎪 Virtual Twin: Stage & Venue Visualizer")
st.caption("Describe your event theme and walk around the 3D venue before you book it.")

with st.sidebar:
    st.header("Settings")
    if not secret_key():
        st.session_state["api_key"] = st.text_input("Gemini API key", type="password")
    st.markdown("Orbit: drag • Zoom: scroll • Pan: right-drag")

with st.form("scene_form"):
    theme = st.text_input("Event theme", "Cyberpunk birthday party with neon lights")
    c1, c2, c3 = st.columns(3)
    width = c1.slider("Room width (m)", 6, 30, 12)
    length = c2.slider("Room length (m)", 6, 30, 10)
    guests = c3.number_input("Guests", 10, 500, 40, step=5)
    go = st.form_submit_button("✨ Generate 3D venue")

if go:
    prompt = (f"Theme: {theme}\nRoom: {width}m wide (x) by {length}m long (z).\n"
              f"Guests: {guests}. Seat everyone at round tables of 6-8 with chairs.")
    with st.spinner("Designing your venue..."):
        try:
            st.session_state["layout"] = generate(prompt)
            st.session_state["theme"] = theme
        except Exception as e:
            st.error(f"Could not generate the layout: {e}")

layout = st.session_state.get("layout")
if layout:
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
        st.caption("Estimates are placeholder unit costs. Edit UNIT_COST in the code.")

    st.divider()
    tweak = st.text_input("Change something", placeholder="Move the stage to the left / add more tables / make lights purple")
    if st.button("Update layout") and tweak:
        prompt = (f"Theme: {st.session_state['theme']}\n"
                  f"Current layout JSON: {json.dumps(layout)}\n"
                  f"Apply this change and return the full updated JSON: {tweak}")
        with st.spinner("Updating..."):
            try:
                st.session_state["layout"] = generate(prompt)
                st.rerun()
            except Exception as e:
                st.error(f"Could not update: {e}")
