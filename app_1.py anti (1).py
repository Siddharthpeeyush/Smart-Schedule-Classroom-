"""
Smart Classroom & Timetable Scheduler  v3.0
Run: python app.py  |  Open: http://localhost:5000

NEW in v3.0  vs v1:
  • Login system (Admin / Faculty roles)
  • Multi-department support + subject codes
  • Electives management & scheduling
  • Faculty leave + substitution system
  • Notice board
  • AI scheduling chat assistant
  • Drag-to-swap timetable slots
  • Dark / Light theme toggle
  • CSV export with institution header
  • Chart.js analytics (4 live charts)
  • Semester archive (save & restore past schedules)
  • Workload overload detection
  • Edit (PUT) for all CRUD entities
  • Conflict AI suggestions tab
  • Custom seed modal
  • Faculty email + building info on rooms
"""

from flask import Flask, request, jsonify, render_template_string, session, Response
import random, io, csv, hashlib, copy, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smartschedule_v3")

# ── STORE ──────────────────────────────────────────────────────────────────
store = {
    "users": [
        {"id":"U1","username":"admin",  "password":hashlib.md5(b"admin123").hexdigest(),  "role":"admin",   "name":"Administrator","facultyId":None},
        {"id":"U2","username":"sharma", "password":hashlib.md5(b"sharma123").hexdigest(), "role":"faculty", "name":"Dr. Sharma",   "facultyId":"F1"},
        {"id":"U3","username":"kapoor", "password":hashlib.md5(b"kapoor123").hexdigest(), "role":"faculty", "name":"Prof. Kapoor", "facultyId":"F2"},
        {"id":"U4","username":"singh",  "password":hashlib.md5(b"singh123").hexdigest(),  "role":"faculty", "name":"Dr. Singh",    "facultyId":"F3"},
        {"id":"U5","username":"verma",  "password":hashlib.md5(b"verma123").hexdigest(),  "role":"faculty", "name":"Ms. Verma",    "facultyId":"F4"},
    ],
    "departments": [
        {"id":"D1","name":"Computer Science & Engineering","code":"CSE"},
        {"id":"D2","name":"Electronics & Communication",   "code":"ECE"},
    ],
    "subjects": [
        {"id":"S1","name":"Mathematics",     "type":"theory","hours":4,"deptId":"D1","code":"MA101","elective":False},
        {"id":"S2","name":"Physics",         "type":"theory","hours":3,"deptId":"D1","code":"PH101","elective":False},
        {"id":"S3","name":"Chemistry Lab",   "type":"lab",   "hours":2,"deptId":"D1","code":"CH101L","elective":False},
        {"id":"S4","name":"Computer Science","type":"theory","hours":3,"deptId":"D1","code":"CS101","elective":False},
        {"id":"S5","name":"English",         "type":"theory","hours":2,"deptId":"D1","code":"EN101","elective":False},
        {"id":"S6","name":"Physics Lab",     "type":"lab",   "hours":2,"deptId":"D1","code":"PH101L","elective":False},
        {"id":"S7","name":"Data Structures", "type":"theory","hours":3,"deptId":"D1","code":"CS201","elective":False},
        {"id":"S8","name":"AI Elective",     "type":"theory","hours":2,"deptId":"D1","code":"CS301E","elective":True},
        {"id":"S9","name":"Circuit Theory",  "type":"theory","hours":3,"deptId":"D2","code":"EC101","elective":False},
    ],
    "faculty": [
        {"id":"F1","name":"Dr. Sharma",  "subjects":["S1","S2"],"availability":["Mon","Tue","Wed","Thu","Fri"],"max_hours":25,"deptId":"D1","email":"sharma@college.edu"},
        {"id":"F2","name":"Prof. Kapoor","subjects":["S3","S6"],"availability":["Mon","Tue","Wed","Thu"],      "max_hours":16,"deptId":"D1","email":"kapoor@college.edu"},
        {"id":"F3","name":"Dr. Singh",   "subjects":["S4","S7"],"availability":["Mon","Tue","Wed","Thu","Fri"],"max_hours":20,"deptId":"D1","email":"singh@college.edu"},
        {"id":"F4","name":"Ms. Verma",   "subjects":["S5","S8"],"availability":["Tue","Thu","Fri"],            "max_hours":12,"deptId":"D1","email":"verma@college.edu"},
        {"id":"F5","name":"Dr. Patel",   "subjects":["S9"],     "availability":["Mon","Tue","Wed","Thu","Fri"],"max_hours":18,"deptId":"D2","email":"patel@college.edu"},
    ],
    "rooms": [
        {"id":"R1","name":"Room 101","type":"theory","capacity":60,"building":"Main","floor":1},
        {"id":"R2","name":"Room 102","type":"theory","capacity":45,"building":"Main","floor":1},
        {"id":"R3","name":"Lab A",   "type":"lab",   "capacity":60,"building":"Main","floor":2},
        {"id":"R4","name":"Lab B",   "type":"lab",   "capacity":60,"building":"Main","floor":2},
        {"id":"R5","name":"Seminar", "type":"theory","capacity":80,"building":"Main","floor":3},
        {"id":"R6","name":"ECE Lab", "type":"lab",   "capacity":60,"building":"ECE Block","floor":1},
    ],
    "batches": [
        {"id":"B1","name":"CSE-A","strength":55,"deptId":"D1","year":2},
        {"id":"B2","name":"CSE-B","strength":50,"deptId":"D1","year":2},
        {"id":"B3","name":"ECE-A","strength":45,"deptId":"D2","year":2},
    ],
    "elective_groups": [
        {"id":"EG1","name":"Open Elective I","subjects":["S8"],"batches":["B1","B2"]},
    ],
    "timetable":{},"conflicts":[],"leaves":[],"substitutions":[],
    "notices": [
        {"id":"N1","title":"Timetable Published","body":"Even Semester 2025 timetable is now live.","author":"Administrator","date":"2025-01-15","priority":"high"},
        {"id":"N2","title":"Lab Maintenance","body":"Lab A under maintenance Wednesday 12-14.","author":"Administrator","date":"2025-01-14","priority":"normal"},
    ],
    "chat_history":[],"archives":[],
    "settings":{"institution":"ABC Institute of Technology","semester":"Even Semester 2025","slot_duration":60,"theme":"dark"},
    "history":[],
}

DAYS  = ["Mon","Tue","Wed","Thu","Fri"]
SLOTS = ["9:00","10:00","11:00","12:00","14:00","15:00","16:00"]

# ── SCHEDULER ──────────────────────────────────────────────────────────────
def generate_timetable(seed=42):
    timetable={}; used_r={}; used_f={}; used_b={}
    fhours={f["id"]:0 for f in store["faculty"]}; conflicts=[]
    sf={}
    for f in store["faculty"]:
        for s in f["subjects"]: sf.setdefault(s,[]).append(f)
    for b in store["batches"]: timetable[b["id"]]={d:{s:None for s in SLOTS} for d in DAYS}
    rng=random.Random(seed)
    for batch in store["batches"]:
        bid=batch["id"]
        for subj in store["subjects"]:
            if subj.get("elective"): continue
            sid,stype,hrs=subj["id"],subj["type"],subj["hours"]; placed=0
            teachers=sf.get(sid,[])
            if not teachers: conflicts.append({"type":"no_faculty","msg":f"No faculty for '{subj[chr(110)+'ame']}'"});continue
            gr=[r for r in store["rooms"] if r["type"]==stype and r["capacity"]>=batch["strength"]]
            if not gr: conflicts.append({"type":"no_room","msg":f"No {stype} room for '{subj['name']}' ({batch['name']})"}); continue
            pairs=[(d,s) for d in DAYS for s in SLOTS]; rng.shuffle(pairs)
            for day,slot in pairs:
                if placed>=hrs: break
                el=[t for t in teachers if day in t["availability"] and (day,slot,t["id"]) not in used_f and fhours[t["id"]]<t.get("max_hours",99)]
                if not el: continue
                teacher=min(el,key=lambda t:fhours[t["id"]])
                room=next((r for r in gr if (day,slot,r["id"]) not in used_r),None)
                if not room: continue
                if (day,slot,bid) in used_b: continue
                timetable[bid][day][slot]={"subject":subj["name"],"subjectId":sid,"type":stype,"code":subj.get("code",""),"faculty":teacher["name"],"facultyId":teacher["id"],"room":room["name"],"roomId":room["id"],"batch":batch["name"],"batchId":bid,"elective":False}
                used_r[(day,slot,room["id"])]=True; used_f[(day,slot,teacher["id"])]=True; used_b[(day,slot,bid)]=True; fhours[teacher["id"]]+=1; placed+=1
            if placed<hrs: conflicts.append({"type":"partial","msg":f"Placed {placed}/{hrs} for '{subj['name']}' ({batch['name']})"})
    for eg in store["elective_groups"]:
        for sid in eg["subjects"]:
            subj=next((s for s in store["subjects"] if s["id"]==sid),None)
            if not subj: continue
            teachers=sf.get(sid,[]); stype=subj["type"]
            for bid in eg["batches"]:
                batch=next((b for b in store["batches"] if b["id"]==bid),None)
                if not batch: continue
                gr=[r for r in store["rooms"] if r["type"]==stype and r["capacity"]>=batch["strength"]]
                if not gr: continue
                placed=0; pairs=[(d,s) for d in DAYS for s in SLOTS]; rng.shuffle(pairs)
                for day,slot in pairs:
                    if placed>=subj["hours"]: break
                    el=[t for t in teachers if day in t["availability"] and (day,slot,t["id"]) not in used_f]
                    if not el: continue
                    teacher=el[0]; room=next((r for r in gr if (day,slot,r["id"]) not in used_r),None)
                    if not room: continue
                    if (day,slot,bid) in used_b: continue
                    timetable[bid][day][slot]={"subject":subj["name"],"subjectId":sid,"type":stype,"code":subj.get("code",""),"faculty":teacher["name"],"facultyId":teacher["id"],"room":room["name"],"roomId":room["id"],"batch":batch["name"],"batchId":bid,"elective":True}
                    used_r[(day,slot,room["id"])]=True; used_f[(day,slot,teacher["id"])]=True; used_b[(day,slot,bid)]=True; placed+=1
    store["timetable"]=timetable; store["conflicts"]=conflicts
    total=sum(1 for b,ds in timetable.items() for d,ss in ds.items() for s,e in ss.items() if e)
    store["history"].insert(0,{"ts":datetime.now().strftime("%d %b %Y, %H:%M"),"classes":total,"conflicts":len(conflicts),"seed":seed})
    store["history"]=store["history"][:15]
    return timetable,conflicts

def ai_sug(cf):
    tips=[]
    for c in cf:
        t=c.get("type","")
        if t=="no_faculty": tips.append(c["msg"].replace("No faculty for","Assign a teacher to")+" — Faculty page.")
        elif t=="no_room":  tips.append(c["msg"]+" — add a room in Rooms page.")
        elif t=="partial":  tips.append(c["msg"]+" — reduce hours or add faculty.")
    return tips

def ai_chat(msg):
    ml=msg.lower(); tt=store["timetable"]
    total=sum(1 for b,ds in tt.items() for d,ss in ds.items() for s,e in ss.items() if e)
    if any(w in ml for w in ["conflict","clash","issue"]): 
        n=len(store["conflicts"])
        if n==0: return "Great news — the timetable has **no conflicts**!"
        return f"There are **{n} conflict(s)**:\n\n"+"\n".join(f"* {c[chr(109)+chr(115)+chr(103)]}" for c in store["conflicts"][:5])+"\n\n**Suggestions:**\n"+"\n".join(f"* {t}" for t in ai_sug(store["conflicts"])[:3])
    elif any(w in ml for w in ["how many classes","total classes"]): return f"The timetable has **{total} classes** across {len(store[chr(98)+chr(97)+chr(116)+chr(99)+chr(104)+chr(101)+chr(115)])} batches."
    elif any(w in ml for w in ["faculty","teacher","workload"]):
        busy={}
        for b,ds in tt.items():
            for d,ss in ds.items():
                for s,e in ss.items():
                    if e: busy[e["faculty"]]=busy.get(e["faculty"],0)+1
        bst=max(busy,key=busy.get) if busy else "None"
        return f"**{len(store['faculty'])} faculty members**. Busiest: **{bst}** ({busy.get(bst,0)} classes). See **Workload** page for details."
    elif any(w in ml for w in ["room","classroom","lab"]): 
        t=[r["name"] for r in store["rooms"] if r["type"]=="theory"]
        l=[r["name"] for r in store["rooms"] if r["type"]=="lab"]
        return f"**{len(t)} theory rooms**: {', '.join(t)}\n**{len(l)} labs**: {', '.join(l)}"
    elif any(w in ml for w in ["batch","section","student"]): return "**Batches:**\n\n"+"\n".join(f"* **{b['name']}** — {b['strength']} students" for b in store["batches"])
    elif any(w in ml for w in ["leave","absent"]): 
        n=len(store["leaves"]); pend=len([l for l in store["leaves"] if l.get("status")=="pending"])
        return f"**{n} leave records** ({pend} pending). Go to **Leaves** page."
    elif any(w in ml for w in ["elective","optional"]): return f"**{len([s for s in store['subjects'] if s.get('elective')])} elective subjects** configured. Manage in **Electives** page."
    elif any(w in ml for w in ["hello","hi","help"]): return "Hello! I am your **SmartSchedule AI**. Ask me about conflicts, workload, rooms, electives, leaves, or any feature!"
    elif any(w in ml for w in ["archive","restore"]): return "Use **Archive** on the Timetable page to save the current schedule. **Archives** shows saved versions."
    elif any(w in ml for w in ["analytics","chart","graph"]): return "The **Analytics** page has 4 live charts: classes per day, faculty workload, room utilization, and subject distribution."
    elif any(w in ml for w in ["export","csv","print"]): return "Use **Export CSV** on the Timetable page for a spreadsheet. Use **Print** for a PDF view."
    elif any(w in ml for w in ["department","dept"]): return "**Departments:**\n\n"+"\n".join(f"* **{d['name']}** ({d['code']})" for d in store["departments"])
    elif any(w in ml for w in ["subject","course"]): 
        core=[s["name"] for s in store["subjects"] if not s.get("elective")]
        elec=[s["name"] for s in store["subjects"] if s.get("elective")]
        return f"**{len(core)} core**: {', '.join(core)}\n**{len(elec)} electives**: {', '.join(elec) if elec else 'None'}"
    else: return "I am not sure. Try asking: 'show conflicts', 'faculty workload', 'show rooms', 'pending leaves', or 'about electives'."

# ── AUTH ───────────────────────────────────────────────────────────────────
def gu(): uid=session.get("user_id"); return next((u for u in store["users"] if u["id"]==uid),None) if uid else None

@app.route("/api/login",  methods=["POST"])
def api_login():
    d=request.json or {}; pwd=hashlib.md5(d.get("password","").encode()).hexdigest()
    u=next((u for u in store["users"] if u["username"]==d.get("username","") and u["password"]==pwd),None)
    if not u: return jsonify({"error":"Invalid credentials"}),401
    session["user_id"]=u["id"]; return jsonify({"id":u["id"],"name":u["name"],"role":u["role"],"facultyId":u["facultyId"]})

@app.route("/api/logout", methods=["POST"])
def api_logout(): session.clear(); return jsonify({"ok":True})

@app.route("/api/me")
def api_me():
    u=gu()
    if not u: return jsonify({"authenticated":False})
    return jsonify({"authenticated":True,"id":u["id"],"name":u["name"],"role":u["role"],"facultyId":u["facultyId"]})

# ── TIMETABLE ROUTES ───────────────────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def api_generate():
    body=request.json or {}; seed=body.get("seed",random.randint(0,99999))
    tt,cf=generate_timetable(seed=seed)
    return jsonify({"timetable":tt,"conflicts":cf,"days":DAYS,"slots":SLOTS,"suggestions":ai_sug(cf),"seed":seed})

@app.route("/api/timetable")
def api_timetable():
    if not store["timetable"]: generate_timetable()
    return jsonify({"timetable":store["timetable"],"conflicts":store["conflicts"],"days":DAYS,"slots":SLOTS,"suggestions":ai_sug(store["conflicts"])})

@app.route("/api/timetable/edit", methods=["POST"])
def api_tt_edit():
    d=request.json or {}; bid,day,slot,entry=d.get("batchId"),d.get("day"),d.get("slot"),d.get("entry")
    if bid and day and slot: store["timetable"].setdefault(bid,{}).setdefault(day,{})[slot]=entry; return jsonify({"ok":True})
    return jsonify({"ok":False}),400

@app.route("/api/timetable/swap", methods=["POST"])
def api_tt_swap():
    d=request.json or {}; bid=d.get("batchId"); sd,ss=d.get("srcDay"),d.get("srcSlot"); dd,ds=d.get("dstDay"),d.get("dstSlot")
    if not all([bid,sd,ss,dd,ds]): return jsonify({"ok":False}),400
    tt=store["timetable"].get(bid,{}); a=copy.deepcopy(tt.get(sd,{}).get(ss)); b=copy.deepcopy(tt.get(dd,{}).get(ds))
    tt.setdefault(sd,{})[ss]=b; tt.setdefault(dd,{})[ds]=a; return jsonify({"ok":True})

@app.route("/api/timetable/export/csv")
def api_export_csv():
    bid=request.args.get("batchId",""); btt=store["timetable"].get(bid,{}); cfg=store["settings"]
    batch=next((b for b in store["batches"] if b["id"]==bid),{"name":bid})
    out=io.StringIO(); w=csv.writer(out)
    w.writerow([cfg["institution"],cfg["semester"]]); w.writerow([])
    w.writerow([f"Timetable: {batch[chr(110)+chr(97)+chr(109)+chr(101)]}"]); w.writerow([]); w.writerow(["Slot"]+DAYS)
    for slot in SLOTS:
        row=[slot]
        for day in DAYS:
            e=btt.get(day,{}).get(slot)
            row.append(f"{e[chr(115)+chr(117)+chr(98)+chr(106)+chr(101)+chr(99)+chr(116)]} ({e.get(chr(99)+chr(111)+chr(100)+chr(101),'')}) | {e[chr(102)+chr(97)+chr(99)+chr(117)+chr(108)+chr(116)+chr(121)]} | {e[chr(114)+chr(111)+chr(111)+chr(109)]}" if e else "—")
        w.writerow(row)
    return Response(out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":f"attachment;filename=timetable_{bid}.csv"})

@app.route("/api/timetable/archive", methods=["POST"])
def api_archive():
    d=request.json or {}; lbl=d.get("label",f"Archive {datetime.now().strftime(chr(37)+chr(100)+chr(32)+chr(37)+chr(98)+chr(32)+chr(37)+chr(89))}")
    arc={"id":f"A{len(store[chr(97)+chr(114)+chr(99)+chr(104)+chr(105)+chr(118)+chr(101)+chr(115)])+1}","label":lbl,"ts":datetime.now().strftime("%d %b %Y, %H:%M"),"timetable":copy.deepcopy(store["timetable"]),"conflicts":copy.deepcopy(store["conflicts"])}
    store["archives"].insert(0,arc); store["archives"]=store["archives"][:5]; return jsonify({"ok":True,"id":arc["id"]})

@app.route("/api/timetable/archive/<aid>", methods=["POST"])
def api_restore_archive(aid):
    arc=next((a for a in store["archives"] if a["id"]==aid),None)
    if not arc: return jsonify({"error":"Not found"}),404
    store["timetable"]=copy.deepcopy(arc["timetable"]); store["conflicts"]=copy.deepcopy(arc["conflicts"]); return jsonify({"ok":True})

@app.route("/api/archives")
def api_archives(): return jsonify([{"id":a["id"],"label":a["label"],"ts":a["ts"]} for a in store["archives"]])

# ── CRUD ───────────────────────────────────────────────────────────────────
def _crud(key,prefix):
    if request.method=="GET": return jsonify(store[key])
    if request.method=="POST":
        d=request.json; d["id"]=prefix+str(len(store[key])+100+random.randint(1,99))
        if key=="faculty": d.setdefault("max_hours",20)
        store[key].append(d); return jsonify(d),201
    if request.method=="PUT":
        d=request.json
        for i,x in enumerate(store[key]):
            if x["id"]==d["id"]: store[key][i]=d; break
        return jsonify(d)
    rid=request.json.get("id"); store[key]=[x for x in store[key] if x["id"]!=rid]; return jsonify({"ok":True})

@app.route("/api/subjects",       methods=["GET","POST","PUT","DELETE"])
def api_subjects():    return _crud("subjects","S")
@app.route("/api/faculty",        methods=["GET","POST","PUT","DELETE"])
def api_faculty():     return _crud("faculty","F")
@app.route("/api/rooms",          methods=["GET","POST","PUT","DELETE"])
def api_rooms():       return _crud("rooms","R")
@app.route("/api/batches",        methods=["GET","POST","PUT","DELETE"])
def api_batches():     return _crud("batches","B")
@app.route("/api/departments",    methods=["GET","POST","PUT","DELETE"])
def api_depts():       return _crud("departments","D")
@app.route("/api/elective_groups",methods=["GET","POST","PUT","DELETE"])
def api_electives():   return _crud("elective_groups","EG")

@app.route("/api/leaves", methods=["GET","POST","DELETE"])
def api_leaves():
    if request.method=="GET": return jsonify(store["leaves"])
    if request.method=="POST":
        d=request.json; d["id"]="L"+str(len(store["leaves"])+1+random.randint(0,99)); d["status"]="pending"
        store["leaves"].append(d); return jsonify(d),201
    lid=request.json.get("id"); store["leaves"]=[l for l in store["leaves"] if l["id"]!=lid]; return jsonify({"ok":True})

@app.route("/api/leaves/<lid>/approve", methods=["POST"])
def api_approve_leave(lid):
    for l in store["leaves"]:
        if l["id"]==lid: l["status"]="approved"; break
    return jsonify({"ok":True})

@app.route("/api/substitutions", methods=["GET","POST","DELETE"])
def api_substitutions():
    if request.method=="GET": return jsonify(store["substitutions"])
    if request.method=="POST":
        d=request.json; d["id"]="SUB"+str(len(store["substitutions"])+1); store["substitutions"].append(d); return jsonify(d),201
    sid=request.json.get("id"); store["substitutions"]=[s for s in store["substitutions"] if s["id"]!=sid]; return jsonify({"ok":True})

@app.route("/api/notices", methods=["GET","POST","DELETE"])
def api_notices():
    if request.method=="GET": return jsonify(store["notices"])
    if request.method=="POST":
        d=request.json; d["id"]="N"+str(len(store["notices"])+1+random.randint(0,99))
        d.setdefault("date",datetime.now().strftime("%Y-%m-%d")); d.setdefault("priority","normal")
        store["notices"].insert(0,d); return jsonify(d),201
    nid=request.json.get("id"); store["notices"]=[n for n in store["notices"] if n["id"]!=nid]; return jsonify({"ok":True})

@app.route("/api/chat", methods=["POST"])
def api_chat():
    msg=request.json.get("message",""); resp=ai_chat(msg)
    store["chat_history"].append({"role":"user","msg":msg,"ts":datetime.now().strftime("%H:%M")})
    store["chat_history"].append({"role":"ai","msg":resp,"ts":datetime.now().strftime("%H:%M")})
    store["chat_history"]=store["chat_history"][-40:]; return jsonify({"response":resp})

@app.route("/api/stats")
def api_stats():
    tt=store["timetable"]; total=0; ru={}; fw={}; sc={}; dc={d:0 for d in DAYS}
    for bid,days in tt.items():
        for d,slots in days.items():
            for s,e in slots.items():
                if e: total+=1; dc[d]+=1; ru[e["roomId"]]=ru.get(e["roomId"],0)+1; fw[e["facultyId"]]=fw.get(e["facultyId"],0)+1; sc[e["subjectId"]]=sc.get(e["subjectId"],0)+1
    denom=max(len(DAYS)*len(SLOTS)*max(len(store["batches"]),1),1)
    return jsonify({"subjects":len(store["subjects"]),"faculty":len(store["faculty"]),"rooms":len(store["rooms"]),"batches":len(store["batches"]),"departments":len(store["departments"]),"classes_scheduled":total,"conflicts":len(store["conflicts"]),"room_utilization":ru,"faculty_workload":fw,"subject_count":sc,"day_distribution":dc,"fill_rate":round(total/denom*100,1),"leaves_pending":len([l for l in store["leaves"] if l.get("status")=="pending"])})

@app.route("/api/history")
def api_history(): return jsonify(store["history"])

@app.route("/api/settings", methods=["GET","POST"])
def api_settings():
    if request.method=="GET": return jsonify(store["settings"])
    store["settings"].update(request.json); return jsonify(store["settings"])

@app.route("/api/report/faculty")
def api_faculty_report():
    tt=store["timetable"]; fmap={f["id"]:f for f in store["faculty"]}; result=[]
    for fid,fdata in fmap.items():
        schedule=[]
        for bid,days in tt.items():
            for d,slots in days.items():
                for s,e in slots.items():
                    if e and e.get("facultyId")==fid: schedule.append({"day":d,"slot":s,"subject":e["subject"],"room":e["room"],"batch":e["batch"]})
        schedule.sort(key=lambda x:(DAYS.index(x["day"]),SLOTS.index(x["slot"])))
        result.append({"id":fid,"name":fdata.get("name",""),"email":fdata.get("email",""),"total_hours":len(schedule),"max_hours":fdata.get("max_hours",20),"schedule":schedule})
    return jsonify(result)

FRONTEND = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartSchedule v3.0</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
[data-theme="dark"]{--bg:#07101e;--sf:#0d1928;--card:#111f32;--card2:#172840;--brd:#1c2d46;--brd2:#27405e;--tx:#dce8ff;--mu:#607090;--mu2:#374f6e;--inp:#0d1928;}
[data-theme="light"]{--bg:#eef3fc;--sf:#fff;--card:#fff;--card2:#f5f8ff;--brd:#d8e6f5;--brd2:#b0cae8;--tx:#1a2540;--mu:#607090;--mu2:#9ab0cc;--inp:#f5f8ff;}
:root{--ac:#4f8ef7;--ac2:#00d4aa;--ac3:#f7914f;--ac4:#c97af5;--dn:#f74f6a;--ok:#3ecf8e;--wn:#f7c24f;--lab:#9b6bf7;--fh:'Syne',sans-serif;--fb:'DM Sans',sans-serif;}
*{box-sizing:border-box;margin:0;padding:0;-webkit-font-smoothing:antialiased}
body{background:var(--bg);color:var(--tx);font-family:var(--fb);min-height:100vh;overflow-x:hidden;transition:background .2s,color .2s}

/* LOGIN */
#ls{position:fixed;inset:0;background:var(--bg);z-index:1000;display:flex;align-items:center;justify-content:center}
.lc{background:var(--card);border:1px solid var(--brd2);border-radius:22px;padding:38px 42px;width:370px;max-width:95vw;box-shadow:0 24px 80px rgba(0,0,0,.4)}
.ll{text-align:center;margin-bottom:24px}
.li{width:52px;height:52px;background:linear-gradient(135deg,var(--ac),var(--ac2));border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:24px;margin:0 auto 10px}
.ll h1{font-family:var(--fh);font-size:19px;font-weight:800}.ll h1 span{color:var(--ac)}
.ll p{font-size:11px;color:var(--mu);margin-top:2px}
.lhint{font-size:11px;color:var(--mu);background:rgba(79,142,247,.07);padding:10px 12px;border-radius:8px;line-height:1.7;margin-bottom:16px}
.lf{margin-bottom:13px}.lf label{display:block;font-size:10px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px}
.lf input{width:100%;padding:10px 13px;background:var(--inp);border:1px solid var(--brd2);border-radius:9px;color:var(--tx);font-family:var(--fb);font-size:14px;outline:none;transition:.15s}
.lf input:focus{border-color:var(--ac);box-shadow:0 0 0 3px rgba(79,142,247,.12)}
.lerr{color:var(--dn);font-size:11.5px;text-align:center;min-height:14px;margin-bottom:10px}

/* SIDEBAR */
#app{display:none}
.sb{position:fixed;left:0;top:0;bottom:0;width:230px;background:var(--sf);border-right:1px solid var(--brd);display:flex;flex-direction:column;z-index:200;transition:background .2s}
.logo{padding:18px 16px 14px;border-bottom:1px solid var(--brd);display:flex;align-items:center;gap:10px}
.logo-ic{width:34px;height:34px;background:linear-gradient(135deg,var(--ac),var(--ac2));border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0}
.logo h1{font-family:var(--fh);font-size:13px;font-weight:800}.logo h1 span{color:var(--ac)}
.logo p{font-size:9.5px;color:var(--mu);margin-top:1px}
.nav{flex:1;padding:8px 0;overflow-y:auto}
.ns{padding:9px 15px 3px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--mu2)}
.ni{display:flex;align-items:center;gap:9px;padding:8px 15px;cursor:pointer;color:var(--mu);font-size:12.5px;font-weight:500;transition:.13s;border-left:2px solid transparent}
.ni:hover{color:var(--tx);background:rgba(79,142,247,.06)}
.ni.active{color:var(--ac);background:rgba(79,142,247,.1);border-left-color:var(--ac)}
.ni .ic{font-size:14px;width:18px;text-align:center;flex-shrink:0}
.ni.ao{display:none}
.nbadge{margin-left:auto;background:var(--dn);color:#fff;font-size:9px;font-weight:700;padding:1px 6px;border-radius:20px;min-width:16px;text-align:center}
.sfoot{padding:10px 15px;border-top:1px solid var(--brd)}
.sf-u{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.sf-av{width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,var(--ac),var(--ac4));display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;color:#fff}
.sf-nm{font-size:12px;font-weight:600}.sf-rl{font-size:10px;color:var(--mu)}
.sf-inst{font-size:10px;color:var(--mu);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tbtn{width:30px;height:17px;border-radius:9px;background:var(--brd2);border:none;cursor:pointer;position:relative;transition:.2s;flex-shrink:0}
.tbtn::after{content:'';position:absolute;width:11px;height:11px;background:#fff;border-radius:50%;top:3px;left:3px;transition:.2s}
[data-theme="light"] .tbtn{background:var(--ac)}
[data-theme="light"] .tbtn::after{transform:translateX(13px)}

/* MAIN */
.main{margin-left:230px;min-height:100vh;padding:22px 26px 56px}
.page{display:none;animation:fi .18s ease}.page.active{display:block}
@keyframes fi{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

/* TOPBAR */
.tb{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:18px;gap:10px;flex-wrap:wrap}
.tb-l h2{font-family:var(--fh);font-size:21px;font-weight:800;line-height:1.1}
.tb-l p{color:var(--mu);font-size:11.5px;margin-top:3px}
.tb-r{display:flex;gap:7px;align-items:center;flex-wrap:wrap}

/* BUTTONS */
.btn{display:inline-flex;align-items:center;gap:5px;padding:7px 14px;border-radius:8px;font-family:var(--fb);font-size:12px;font-weight:600;cursor:pointer;border:none;transition:.13s;white-space:nowrap}
.btn:active{transform:scale(.97)}
.bp{background:var(--ac);color:#fff}.bp:hover{background:#3d7de8}
.bg{background:transparent;color:var(--mu);border:1px solid var(--brd2)}.bg:hover{color:var(--tx);border-color:var(--ac)}
.bd{background:var(--dn);color:#fff}.bd:hover{filter:brightness(1.1)}
.bs{background:var(--ok);color:#07291a}.bs:hover{filter:brightness(1.1)}
.bgl{background:linear-gradient(135deg,var(--ac),var(--ac2));color:#03201a;font-weight:800;box-shadow:0 4px 18px rgba(0,212,170,.2)}
.bgl:hover{filter:brightness(1.05);box-shadow:0 6px 24px rgba(0,212,170,.32)}
.bsm{padding:5px 11px;font-size:11px;border-radius:6px}

/* STAT CARDS */
.sg{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:11px;margin-bottom:18px}
.sc{background:var(--card);border:1px solid var(--brd);border-radius:11px;padding:15px 17px;position:relative;overflow:hidden;transition:.18s;cursor:default}
.sc:hover{border-color:var(--c,var(--ac));box-shadow:0 0 0 1px var(--c,var(--ac)),0 5px 16px rgba(0,0,0,.18)}
.sc::before{content:'';position:absolute;inset:0;background:var(--c,var(--ac));opacity:.04}
.sc .n{font-family:var(--fh);font-size:27px;font-weight:800;line-height:1;color:var(--c,var(--ac));margin-bottom:2px}
.sc .l{font-size:10px;color:var(--mu);text-transform:uppercase;letter-spacing:.5px;font-weight:600}
.sc .ei{position:absolute;right:11px;top:11px;font-size:22px;opacity:.11}

/* DATA CARDS */
.dg{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:11px}
.dc{background:var(--card);border:1px solid var(--brd);border-radius:11px;padding:14px 16px;display:flex;flex-direction:column;gap:6px;transition:.14s}
.dc:hover{border-color:var(--brd2);transform:translateY(-2px);box-shadow:0 5px 16px rgba(0,0,0,.18)}
.dch{display:flex;align-items:center;justify-content:space-between;gap:6px}
.dct{font-weight:700;font-size:13px;display:flex;align-items:center;gap:6px}
.dcid{font-size:9px;color:var(--mu2);background:var(--sf);padding:2px 6px;border-radius:20px;border:1px solid var(--brd);font-family:monospace}
.dcs{font-size:11.5px;color:var(--mu);line-height:1.5}
.dctg{display:flex;flex-wrap:wrap;gap:4px}
.dca{display:flex;gap:6px;margin-top:3px;padding-top:8px;border-top:1px solid var(--brd)}

/* BADGES */
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600}
.bt{background:rgba(79,142,247,.14);color:var(--ac)}.bl{background:rgba(155,107,247,.14);color:var(--lab)}
.bav{background:rgba(62,207,142,.12);color:var(--ok)}.bd2{background:rgba(247,79,106,.12);color:var(--dn)}
.bw{background:rgba(247,194,79,.12);color:var(--wn)}.be{background:rgba(0,212,170,.12);color:var(--ac2)}
.bday{background:rgba(79,142,247,.12);color:var(--ac);font-size:9.5px;padding:1px 6px}

/* TIMETABLE */
.ttbar{display:flex;align-items:center;gap:9px;margin-bottom:12px;flex-wrap:wrap}
.ttbar select{background:var(--card);border:1px solid var(--brd);color:var(--tx);padding:6px 10px;border-radius:7px;font-family:var(--fb);font-size:12px;outline:none}
.ttbar select:focus{border-color:var(--ac)}
.ttwrap{overflow-x:auto;border-radius:11px;border:1px solid var(--brd);box-shadow:0 4px 18px rgba(0,0,0,.18)}
table.tt{width:100%;border-collapse:collapse;min-width:640px}
table.tt thead{background:var(--sf)}
table.tt th{padding:9px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:var(--mu);text-align:left;border-bottom:1px solid var(--brd)}
table.tt th:first-child{width:66px;text-align:center}
table.tt td{padding:5px 6px;border-bottom:1px solid var(--brd);border-right:1px solid var(--brd);vertical-align:top;min-width:118px}
table.tt td:first-child{font-size:10.5px;font-weight:700;color:var(--mu);background:var(--sf);text-align:center}
table.tt tr:last-child td{border-bottom:none}
table.tt tr:hover td:not(:first-child){background:rgba(79,142,247,.03)}
.ce{height:50px;display:flex;align-items:center;justify-content:center;opacity:.18;font-size:10px;color:var(--mu);cursor:pointer}
.ce:hover{opacity:.45;color:var(--ac2)}
.cc{background:rgba(79,142,247,.08);border:1px solid rgba(79,142,247,.22);border-radius:7px;padding:6px 8px;font-size:10.5px;line-height:1.5;cursor:grab;transition:.12s;position:relative;user-select:none}
.cc:hover{background:rgba(79,142,247,.14);border-color:var(--ac)}
.cc.lb{background:rgba(155,107,247,.09);border-color:rgba(155,107,247,.28)}.cc.lb:hover{background:rgba(155,107,247,.16)}
.cc.el{border-style:dashed;border-color:var(--ac2)}
.cc.dg2{opacity:.45;transform:scale(.96)}.cc.dov{border-color:var(--wn)!important;background:rgba(247,194,79,.1)!important}
.cc .cs{font-weight:700;color:var(--tx);margin-bottom:1px}.cc .cm{color:var(--mu);font-size:9.5px}
.cc .cdl{position:absolute;top:3px;right:3px;background:var(--dn);color:#fff;border:none;border-radius:4px;font-size:9px;padding:1px 5px;cursor:pointer;display:none;font-family:var(--fb)}
.cc:hover .cdl{display:block}
.slbl{font-size:9px;color:var(--mu2);display:block;margin-bottom:1px}

/* CONFLICT PANEL */
.cpn{background:rgba(247,79,106,.05);border:1px solid rgba(247,79,106,.2);border-radius:11px;padding:12px 15px;margin-bottom:14px}
.cpn .ch{display:flex;align-items:center;gap:7px;margin-bottom:8px}
.cpn .ch h4{font-family:var(--fh);font-size:11.5px;font-weight:700;color:var(--dn)}
.cpn .ch span{font-size:10px;color:var(--mu)}
.ctabs{display:flex;border-bottom:1px solid var(--brd);margin-bottom:7px}
.ctab{padding:5px 12px;font-size:11px;font-weight:600;cursor:pointer;color:var(--mu);border-bottom:2px solid transparent;transition:.12s}
.ctab.active{color:var(--dn);border-bottom-color:var(--dn)}
.cl{list-style:none;display:flex;flex-direction:column;gap:4px}
.cl li{font-size:11px;color:var(--mu);padding-left:13px;position:relative;line-height:1.5}
.cl li::before{content:"⚠";position:absolute;left:0;font-size:9px;top:1px}
.cl.tips li::before{content:"➜";color:var(--ac2)}.cl.tips li{color:var(--tx)}

/* WORKLOAD BARS */
.wr{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.wn2{width:112px;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wt{flex:1;height:8px;background:var(--brd);border-radius:4px;overflow:hidden}
.wf{height:100%;border-radius:4px;transition:width .5s cubic-bezier(.4,0,.2,1)}
.wlb{font-size:11px;color:var(--mu);width:46px;text-align:right}
.wov{color:var(--dn)!important}

/* CHARTS */
.cgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px}
.cbox{background:var(--card);border:1px solid var(--brd);border-radius:11px;padding:14px 16px}
.cbox h4{font-family:var(--fh);font-size:12.5px;font-weight:700;margin-bottom:12px}
.cwrap{position:relative;height:190px}

/* MODAL */
.mo{position:fixed;inset:0;background:rgba(0,0,10,.72);backdrop-filter:blur(5px);z-index:600;display:none;align-items:center;justify-content:center;padding:16px}
.mo.open{display:flex}
.mbox{background:var(--card2);border:1px solid var(--brd2);border-radius:16px;padding:22px 24px;width:490px;max-width:100%;max-height:90vh;overflow-y:auto;box-shadow:0 24px 60px rgba(0,0,0,.5)}
.mbox h3{font-family:var(--fh);font-size:15px;font-weight:800;margin-bottom:14px}
.fg{margin-bottom:12px}
.fg label{display:block;font-size:10px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
.fg input,.fg select,.fg textarea{width:100%;padding:8px 11px;background:var(--inp);border:1px solid var(--brd);border-radius:7px;color:var(--tx);font-family:var(--fb);font-size:13px;outline:none;transition:.13s}
.fg input:focus,.fg select:focus,.fg textarea:focus{border-color:var(--ac);box-shadow:0 0 0 3px rgba(79,142,247,.1)}
.frow{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.dchips{display:flex;gap:5px;flex-wrap:wrap;margin-top:3px}
.dchip{padding:3px 10px;border-radius:20px;border:1px solid var(--brd);font-size:11px;font-weight:600;cursor:pointer;background:transparent;color:var(--mu);transition:.12s;user-select:none}
.dchip.on{background:rgba(79,142,247,.18);border-color:var(--ac);color:var(--ac)}
.fa{display:flex;gap:7px;justify-content:flex-end;margin-top:13px;padding-top:12px;border-top:1px solid var(--brd)}

/* SECTION CARD */
.scard{background:var(--card);border:1px solid var(--brd);border-radius:11px;padding:15px 17px;margin-bottom:14px}
.scard h3{font-family:var(--fh);font-size:13px;font-weight:700;margin-bottom:11px;display:flex;align-items:center;gap:6px}

/* MINI TABLE */
.mt{width:100%;border-collapse:collapse}
.mt th{font-size:9.5px;text-transform:uppercase;letter-spacing:.4px;color:var(--mu);padding:5px 8px;border-bottom:1px solid var(--brd);text-align:left;font-weight:700}
.mt td{font-size:11.5px;padding:7px 8px;border-bottom:1px solid var(--brd);color:var(--tx)}
.mt tr:last-child td{border-bottom:none}
.mt tr:hover td{background:rgba(79,142,247,.03)}

/* TABS */
.tabs{display:flex;border-bottom:1px solid var(--brd);margin-bottom:14px}
.tab{padding:7px 14px;font-size:12px;font-weight:600;cursor:pointer;color:var(--mu);border-bottom:2px solid transparent;transition:.12s}
.tab.active{color:var(--ac);border-bottom-color:var(--ac)}

/* HERO */
.hero{background:linear-gradient(135deg,var(--card) 0%,rgba(79,142,247,.1) 55%,rgba(0,212,170,.07) 100%);border:1px solid var(--brd);border-radius:16px;padding:22px 26px;margin-bottom:18px;position:relative;overflow:hidden}
.hero::after{content:"🎓";position:absolute;right:26px;top:50%;transform:translateY(-50%);font-size:68px;opacity:.08;pointer-events:none}
.hero h3{font-family:var(--fh);font-size:17px;font-weight:800;margin-bottom:4px}
.hero p{color:var(--mu);font-size:12px;max-width:460px;line-height:1.7}
.hchips{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.hchip{background:rgba(79,142,247,.1);border:1px solid rgba(79,142,247,.2);border-radius:20px;padding:3px 10px;font-size:10px;font-weight:600;color:var(--ac)}

/* HISTORY */
.hrow{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--brd)}
.hrow:last-child{border-bottom:none}
.hts{font-size:10px;color:var(--mu);width:120px;flex-shrink:0}
.hb{flex:1;font-size:11.5px}

/* SETTINGS */
.setrow{display:flex;align-items:center;justify-content:space-between;padding:11px 0;border-bottom:1px solid var(--brd);gap:10px}
.setrow:last-child{border-bottom:none}
.setrow .sl h4{font-size:12.5px;font-weight:600;margin-bottom:2px}
.setrow .sl p{font-size:11px;color:var(--mu)}
.setrow .sr input,.setrow .sr select{background:var(--inp);border:1px solid var(--brd);color:var(--tx);padding:6px 10px;border-radius:7px;font-family:var(--fb);font-size:12px;outline:none;min-width:160px}

/* SEARCH */
.srch{display:flex;align-items:center;gap:7px;background:var(--card);border:1px solid var(--brd);border-radius:8px;padding:7px 10px;margin-bottom:12px;width:100%;max-width:330px}
.srch input{background:transparent;border:none;color:var(--tx);font-family:var(--fb);font-size:12.5px;outline:none;flex:1}

/* NOTICE BOARD */
.nc{background:var(--card);border:1px solid var(--brd);border-radius:11px;padding:13px 15px;margin-bottom:10px;transition:.14s}
.nc:hover{border-color:var(--brd2)}
.nc.high{border-left:3px solid var(--dn)}.nc.normal{border-left:3px solid var(--ac)}
.nc-hd{display:flex;align-items:flex-start;justify-content:space-between;gap:7px;margin-bottom:5px}
.nc-ti{font-weight:700;font-size:13px}
.nc-mt{font-size:10.5px;color:var(--mu);margin-bottom:4px}
.nc-bd{font-size:12.5px;line-height:1.6}

/* AI CHAT */
.chat-wrap{display:flex;flex-direction:column;height:calc(100vh - 160px);max-height:660px}
.chat-msgs{flex:1;overflow-y:auto;padding:12px;background:var(--card);border:1px solid var(--brd);border-radius:11px 11px 0 0;display:flex;flex-direction:column;gap:9px}
.chat-ir{display:flex;gap:7px;padding:9px;background:var(--card2);border:1px solid var(--brd);border-top:none;border-radius:0 0 11px 11px}
.chat-ir input{flex:1;background:var(--inp);border:1px solid var(--brd);color:var(--tx);padding:8px 12px;border-radius:7px;font-family:var(--fb);font-size:13px;outline:none}
.chat-ir input:focus{border-color:var(--ac)}
.cb{max-width:80%;padding:9px 12px;border-radius:11px;font-size:12px;line-height:1.6}
.cb.user{background:rgba(79,142,247,.18);align-self:flex-end;color:var(--tx)}
.cb.ai{background:var(--card2);border:1px solid var(--brd);align-self:flex-start}
.cb .ts{font-size:9px;color:var(--mu);margin-top:3px}
.chat-typing{font-size:11px;color:var(--mu);padding:5px 12px;align-self:flex-start}

/* LEAVES */
.lvc{background:var(--card);border:1px solid var(--brd);border-radius:11px;padding:12px 14px;margin-bottom:9px;display:flex;align-items:center;gap:11px;flex-wrap:wrap}
.lvi{flex:1;min-width:180px}
.lv-nm{font-weight:700;font-size:12.5px;margin-bottom:2px}
.lv-mt{font-size:11px;color:var(--mu)}
.sbadge{padding:3px 10px;border-radius:20px;font-size:10px;font-weight:700}
.sp{background:rgba(247,194,79,.15);color:var(--wn)}
.sa{background:rgba(62,207,142,.15);color:var(--ok)}

/* EMPTY */
.empty{text-align:center;padding:38px 20px;color:var(--mu)}
.empty .ei{font-size:34px;margin-bottom:8px;opacity:.5}
.empty p{font-size:13px}

/* TOAST */
#toast{position:fixed;bottom:20px;right:20px;background:var(--card2);border:1px solid var(--brd);border-radius:9px;padding:9px 15px;font-size:12px;box-shadow:0 8px 28px rgba(0,0,0,.4);transform:translateY(130%);transition:.25s cubic-bezier(.4,0,.2,1);z-index:999;display:flex;align-items:center;gap:7px;max-width:280px}
#toast.show{transform:translateY(0)}
#toast.ok{border-color:var(--ok);color:var(--ok)}
#toast.err{border-color:var(--dn);color:var(--dn)}
#toast.info{border-color:var(--ac);color:var(--ac)}

/* PRINT */
@media print{.sb,.tb-r,.ttbar .btn,#toast,.np{display:none!important}.main{margin-left:0;padding:0}.ttwrap{border:none;box-shadow:none}table.tt{font-size:10px}}

::-webkit-scrollbar{width:4px;height:4px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--brd2);border-radius:3px}
@media(max-width:860px){.sb{display:none}.main{margin-left:0;padding:14px 12px 46px}}
@media(max-width:560px){.sg{grid-template-columns:1fr 1fr}.dg{grid-template-columns:1fr}.cgrid{grid-template-columns:1fr}.frow{grid-template-columns:1fr}}
</style></head>
<body>

<!-- LOGIN -->
<div id="ls">
  <div class="lc">
    <div class="ll"><div class="li">🗓</div><h1>Smart<span>Schedule</span></h1><p>AI Timetable Scheduler v3.0</p></div>
    <div class="lhint"><b>Demo credentials</b><br>Admin: <code>admin</code> / <code>admin123</code><br>Faculty: <code>sharma</code> / <code>sharma123</code></div>
    <div class="lf"><label>Username</label><input id="l-u" placeholder="Username" autocomplete="username"></div>
    <div class="lf"><label>Password</label><input id="l-p" type="password" placeholder="Password" autocomplete="current-password" onkeydown="if(event.key==='Enter')doLogin()"></div>
    <div class="lerr" id="l-err"></div>
    <button class="btn bgl" style="width:100%;justify-content:center;padding:11px" onclick="doLogin()">Sign In →</button>
  </div>
</div>

<!-- APP -->
<div id="app">
<nav class="sb">
  <div class="logo"><div class="logo-ic">🗓</div><div><h1>Smart<span>Schedule</span></h1><p id="logo-sem">v3.0</p></div></div>
  <div class="nav">
    <div class="ns">Main</div>
    <div class="ni active" data-page="dashboard" onclick="nav(this)"><span class="ic">📊</span>Dashboard</div>
    <div class="ni" data-page="timetable"  onclick="nav(this)"><span class="ic">📅</span>Timetable<span class="nbadge" id="nb-cf" style="display:none">0</span></div>
    <div class="ni" data-page="analytics"  onclick="nav(this)"><span class="ic">📉</span>Analytics</div>
    <div class="ni" data-page="notices"    onclick="nav(this)"><span class="ic">📢</span>Notice Board</div>
    <div class="ni" data-page="assistant"  onclick="nav(this)"><span class="ic">🤖</span>AI Assistant</div>
    <div class="ns">Academic Data</div>
    <div class="ni ao" data-page="subjects"   onclick="nav(this)"><span class="ic">📚</span>Subjects</div>
    <div class="ni ao" data-page="faculty"    onclick="nav(this)"><span class="ic">👨‍🏫</span>Faculty</div>
    <div class="ni ao" data-page="rooms"      onclick="nav(this)"><span class="ic">🏫</span>Rooms</div>
    <div class="ni ao" data-page="batches"    onclick="nav(this)"><span class="ic">👥</span>Batches</div>
    <div class="ni ao" data-page="electives"  onclick="nav(this)"><span class="ic">📘</span>Electives</div>
    <div class="ns">Reports</div>
    <div class="ni" data-page="workload"   onclick="nav(this)"><span class="ic">📈</span>Workload</div>
    <div class="ni" data-page="leaves"     onclick="nav(this)"><span class="ic">🏖</span>Leaves<span class="nbadge" id="nb-lv" style="display:none">0</span></div>
    <div class="ns">System</div>
    <div class="ni ao" data-page="settings" onclick="nav(this)"><span class="ic">⚙️</span>Settings</div>
  </div>
  <div class="sfoot">
    <div class="sf-u">
      <div class="sf-av" id="sf-av">A</div>
      <div><div class="sf-nm" id="sf-nm">—</div><div class="sf-rl" id="sf-rl">—</div></div>
      <button class="btn bg bsm" style="margin-left:auto;padding:4px 8px" onclick="doLogout()">↩</button>
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between">
      <div class="sf-inst" id="sf-inst">—</div>
      <button class="tbtn" onclick="toggleTheme()" title="Toggle theme"></button>
    </div>
  </div>
</nav>

<main class="main">

<!-- DASHBOARD -->
<div class="page active" id="page-dashboard">
  <div class="tb">
    <div class="tb-l"><h2>Dashboard</h2><p>Your scheduling overview at a glance</p></div>
    <div class="tb-r">
      <button class="btn bg bsm np" onclick="nav(document.querySelector('[data-page=settings]'))">⚙</button>
      <button class="btn bgl np" onclick="doGenerate()">⚡ Generate Timetable</button>
    </div>
  </div>
  <div class="hero">
    <h3 id="hero-inst">Smart Classroom &amp; Timetable Scheduler</h3>
    <p>Automated, clash-free scheduling with elective support, workload balancing, and full NEP 2020 compliance.</p>
    <div class="hchips"><span class="hchip" id="hero-sem">—</span><span class="hchip">NEP 2020</span><span class="hchip">Clash-Free</span><span class="hchip">Elective Support</span><span class="hchip">Multi-Dept</span></div>
  </div>
  <div class="sg">
    <div class="sc" style="--c:var(--ac)"><div class="ei">📚</div><div class="n" id="st-s">—</div><div class="l">Subjects</div></div>
    <div class="sc" style="--c:var(--ac4)"><div class="ei">👨‍🏫</div><div class="n" id="st-f">—</div><div class="l">Faculty</div></div>
    <div class="sc" style="--c:var(--ac3)"><div class="ei">🏫</div><div class="n" id="st-r">—</div><div class="l">Rooms</div></div>
    <div class="sc" style="--c:var(--ac2)"><div class="ei">👥</div><div class="n" id="st-b">—</div><div class="l">Batches</div></div>
    <div class="sc" style="--c:var(--ok)"><div class="ei">✅</div><div class="n" id="st-c">—</div><div class="l">Classes</div></div>
    <div class="sc" style="--c:var(--dn)"><div class="ei">⚠️</div><div class="n" id="st-cf">—</div><div class="l">Conflicts</div></div>
    <div class="sc" style="--c:var(--wn)"><div class="ei">📊</div><div class="n" id="st-fr">—%</div><div class="l">Fill Rate</div></div>
    <div class="sc" style="--c:var(--ac2)"><div class="ei">🏛</div><div class="n" id="st-d">—</div><div class="l">Departments</div></div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:13px">
    <div class="scard"><h3>🏫 Room Utilization</h3><div id="room-util"></div></div>
    <div class="scard"><h3>📋 Generation History</h3><div id="gen-hist"></div></div>
  </div>
</div>

<!-- TIMETABLE -->
<div class="page" id="page-timetable">
  <div class="tb">
    <div class="tb-l"><h2>Timetable</h2><p>Drag cells to swap · Click ✕ to clear · Dashed = Elective</p></div>
    <div class="tb-r">
      <button class="btn bg bsm np" onclick="exportCSV()">⬇ CSV</button>
      <button class="btn bg bsm np" onclick="archivePrompt()">📦 Archive</button>
      <button class="btn bg bsm np" onclick="openArchives()">🗂 Archives</button>
      <button class="btn bg bsm np" onclick="openSeedModal()">🎲 Seed</button>
      <button class="btn bgl np" onclick="doGenerate(true)">⚡ Regenerate</button>
    </div>
  </div>
  <div id="tt-cf-area"></div>
  <div class="ttbar">
    <label style="font-size:11.5px;color:var(--mu)">View:</label>
    <select id="tt-view" onchange="onViewChange()">
      <option value="batch">By Batch</option>
      <option value="faculty">By Faculty</option>
      <option value="room">By Room</option>
    </select>
    <label style="font-size:11.5px;color:var(--mu)" id="tt-sel-lbl">Batch:</label>
    <select id="tt-entity" onchange="renderTT()"></select>
    <button class="btn bg bsm np" style="margin-left:auto" onclick="window.print()">🖨 Print</button>
  </div>
  <div class="ttwrap"><table class="tt" id="tt-tbl"></table></div>
</div>

<!-- ANALYTICS -->
<div class="page" id="page-analytics">
  <div class="tb">
    <div class="tb-l"><h2>Analytics</h2><p>Live scheduling insights &amp; distribution charts</p></div>
    <div class="tb-r"><button class="btn bg bsm" onclick="loadAnalytics()">↻ Refresh</button></div>
  </div>
  <div class="cgrid">
    <div class="cbox"><h4>📅 Classes per Day</h4><div class="cwrap"><canvas id="ch-day"></canvas></div></div>
    <div class="cbox"><h4>👨‍🏫 Faculty Workload</h4><div class="cwrap"><canvas id="ch-fac"></canvas></div></div>
    <div class="cbox"><h4>🏫 Room Utilization</h4><div class="cwrap"><canvas id="ch-room"></canvas></div></div>
    <div class="cbox"><h4>📚 Subject Distribution</h4><div class="cwrap"><canvas id="ch-subj"></canvas></div></div>
  </div>
</div>

<!-- NOTICE BOARD -->
<div class="page" id="page-notices">
  <div class="tb">
    <div class="tb-l"><h2>Notice Board</h2><p>Announcements &amp; updates</p></div>
    <div class="tb-r ao"><button class="btn bp" onclick="openModal('notice')">+ Post Notice</button></div>
  </div>
  <div id="notices-list"></div>
</div>

<!-- AI ASSISTANT -->
<div class="page" id="page-assistant">
  <div class="tb">
    <div class="tb-l"><h2>AI Assistant</h2><p>Ask anything about your timetable &amp; scheduling</p></div>
    <div class="tb-r"><button class="btn bg bsm" onclick="clearChat()">🗑 Clear</button></div>
  </div>
  <div class="chat-wrap">
    <div class="chat-msgs" id="chat-msgs">
      <div class="cb ai">👋 Hello! I'm your <b>SmartSchedule AI</b>.<br><br>Ask me about conflicts, workload, rooms, electives, or any feature!<div class="ts">Now</div></div>
    </div>
    <div class="chat-ir">
      <input id="chat-in" placeholder="Ask about conflicts, faculty, rooms, electives…" onkeydown="if(event.key==='Enter')sendChat()">
      <button class="btn bgl" onclick="sendChat()">Send ➤</button>
    </div>
  </div>
  <div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:9px">
    <button class="btn bg bsm" onclick="qa('show conflicts')">⚠ Conflicts</button>
    <button class="btn bg bsm" onclick="qa('how many classes')">📊 Stats</button>
    <button class="btn bg bsm" onclick="qa('faculty workload')">👨‍🏫 Workload</button>
    <button class="btn bg bsm" onclick="qa('show rooms')">🏫 Rooms</button>
    <button class="btn bg bsm" onclick="qa('about electives')">📘 Electives</button>
    <button class="btn bg bsm" onclick="qa('pending leaves')">🏖 Leaves</button>
    <button class="btn bg bsm" onclick="qa('analytics charts')">📉 Analytics</button>
    <button class="btn bg bsm" onclick="qa('how to archive')">📦 Archive</button>
  </div>
</div>

<!-- SUBJECTS -->
<div class="page" id="page-subjects">
  <div class="tb"><div class="tb-l"><h2>Subjects</h2><p>Manage course subjects, types &amp; codes</p></div><div class="tb-r"><button class="btn bp" onclick="openModal('subject')">+ Add Subject</button></div></div>
  <div class="srch"><span>🔍</span><input placeholder="Search subjects…" oninput="fc('subj-grid',this.value)"></div>
  <div class="dg" id="subj-grid"></div>
</div>

<!-- FACULTY -->
<div class="page" id="page-faculty">
  <div class="tb"><div class="tb-l"><h2>Faculty</h2><p>Manage members, availability &amp; assignments</p></div><div class="tb-r"><button class="btn bp" onclick="openModal('faculty')">+ Add Faculty</button></div></div>
  <div class="srch"><span>🔍</span><input placeholder="Search faculty…" oninput="fc('fac-grid',this.value)"></div>
  <div class="dg" id="fac-grid"></div>
</div>

<!-- ROOMS -->
<div class="page" id="page-rooms">
  <div class="tb"><div class="tb-l"><h2>Rooms</h2><p>Classrooms &amp; laboratories</p></div><div class="tb-r"><button class="btn bp" onclick="openModal('room')">+ Add Room</button></div></div>
  <div class="srch"><span>🔍</span><input placeholder="Search rooms…" oninput="fc('room-grid',this.value)"></div>
  <div class="dg" id="room-grid"></div>
</div>

<!-- BATCHES -->
<div class="page" id="page-batches">
  <div class="tb"><div class="tb-l"><h2>Batches</h2><p>Student batches &amp; sections</p></div><div class="tb-r"><button class="btn bp" onclick="openModal('batch')">+ Add Batch</button></div></div>
  <div class="srch"><span>🔍</span><input placeholder="Search batches…" oninput="fc('bat-grid',this.value)"></div>
  <div class="dg" id="bat-grid"></div>
</div>

<!-- ELECTIVES -->
<div class="page" id="page-electives">
  <div class="tb"><div class="tb-l"><h2>Electives</h2><p>Optional subject groups &amp; batch assignments</p></div><div class="tb-r"><button class="btn bp" onclick="openModal('elective')">+ Add Group</button></div></div>
  <div class="dg" id="elec-grid"></div>
</div>

<!-- WORKLOAD -->
<div class="page" id="page-workload">
  <div class="tb"><div class="tb-l"><h2>Workload Report</h2><p>Faculty schedule &amp; load analysis</p></div><div class="tb-r"><button class="btn bg bsm" onclick="loadWorkload()">↻ Refresh</button></div></div>
  <div class="scard"><h3>👨‍🏫 Load Overview</h3><div id="wl-bars"></div></div>
  <div class="scard"><h3>📋 Detailed Schedules</h3><div class="tabs" id="wl-tabs"></div><div id="wl-det"></div></div>
</div>

<!-- LEAVES -->
<div class="page" id="page-leaves">
  <div class="tb"><div class="tb-l"><h2>Leaves &amp; Substitutions</h2><p>Manage faculty absence &amp; cover arrangements</p></div><div class="tb-r"><button class="btn bp" onclick="openModal('leave')">+ Apply Leave</button></div></div>
  <div class="tabs"><div class="tab active" onclick="lvTab(0,this)">Leave Requests</div><div class="tab" onclick="lvTab(1,this)">Substitutions</div></div>
  <div id="lv-panel"></div>
  <div id="sub-panel" style="display:none"></div>
</div>

<!-- SETTINGS -->
<div class="page" id="page-settings">
  <div class="tb"><div class="tb-l"><h2>Settings</h2><p>Institution &amp; scheduling configuration</p></div><div class="tb-r"><button class="btn bp" onclick="saveSettings()">💾 Save</button></div></div>
  <div class="scard">
    <h3>🏛 Institution</h3>
    <div class="setrow"><div class="sl"><h4>Institution Name</h4><p>Shown in all headers and exports</p></div><div class="sr"><input id="set-inst"></div></div>
    <div class="setrow"><div class="sl"><h4>Semester / Term</h4><p>Current academic period label</p></div><div class="sr"><input id="set-sem"></div></div>
  </div>
  <div class="scard">
    <h3>⏰ Schedule</h3>
    <div class="setrow"><div class="sl"><h4>Slot Duration</h4><p>Minutes per class period</p></div><div class="sr"><select id="set-dur"><option value="45">45 min</option><option value="60">60 min</option><option value="90">90 min</option></select></div></div>
  </div>
  <div class="scard">
    <h3>👤 User Accounts</h3>
    <p style="font-size:12px;color:var(--mu);margin-bottom:10px">Demo accounts — update passwords in production.</p>
    <table class="mt"><thead><tr><th>Username</th><th>Name</th><th>Role</th></tr></thead>
    <tbody><tr><td>admin</td><td>Administrator</td><td><span class="badge bt">admin</span></td></tr>
    <tr><td>sharma</td><td>Dr. Sharma</td><td><span class="badge bav">faculty</span></td></tr>
    <tr><td>kapoor</td><td>Prof. Kapoor</td><td><span class="badge bav">faculty</span></td></tr>
    <tr><td>singh</td><td>Dr. Singh</td><td><span class="badge bav">faculty</span></td></tr>
    <tr><td>verma</td><td>Ms. Verma</td><td><span class="badge bav">faculty</span></td></tr></tbody></table>
  </div>
  <div class="scard">
    <h3>🗑 Danger Zone</h3>
    <div class="setrow"><div class="sl"><h4>Reset &amp; Regenerate</h4><p>Clear timetable and regenerate fresh</p></div><div class="sr"><button class="btn bd bsm" onclick="doGenerate(true)">Reset &amp; Regen</button></div></div>
  </div>
</div>

</main>
</div><!-- /app -->

<div class="mo" id="mo" onclick="cmo(event)"><div class="mbox" id="mbox"></div></div>
<div id="toast"></div>

<script>
// ═══ STATE ══════════════════════════════════════════════════════
let ttData=null,lastSeed=null,me=null,_charts={};
const DAYS=["Mon","Tue","Wed","Thu","Fri"],SLOTS=["9:00","10:00","11:00","12:00","14:00","15:00","16:00"],ALLD=["Mon","Tue","Wed","Thu","Fri"];

// ═══ AUTH ════════════════════════════════════════════════════════
async function doLogin(){
  document.getElementById('l-err').textContent='';
  try{
    me=await api('/api/login','POST',{username:document.getElementById('l-u').value.trim(),password:document.getElementById('l-p').value});
    document.getElementById('ls').style.display='none';
    document.getElementById('app').style.display='block';
    applyRole(me);await initApp();
  }catch(e){document.getElementById('l-err').textContent='Invalid username or password.';}
}
async function doLogout(){
  await api('/api/logout','POST');me=null;
  document.getElementById('app').style.display='none';
  document.getElementById('ls').style.display='flex';
  document.getElementById('l-p').value='';
}
function applyRole(u){
  document.getElementById('sf-nm').textContent=u.name;
  document.getElementById('sf-av').textContent=u.name[0];
  document.getElementById('sf-rl').textContent=u.role==='admin'?'Administrator':'Faculty';
  if(u.role==='admin') document.querySelectorAll('.ao').forEach(el=>el.style.display='flex');
}

// ═══ NAV ═════════════════════════════════════════════════════════
function nav(el){
  const pg=el.dataset.page;
  document.querySelectorAll('.ni').forEach(n=>n.classList.remove('active'));el.classList.add('active');
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById('page-'+pg).classList.add('active');
  ({dashboard:loadDash,timetable:loadTT,analytics:loadAnalytics,notices:loadNotices,
    assistant:()=>{},subjects:loadSubjects,faculty:loadFaculty,rooms:loadRooms,
    batches:loadBatches,electives:loadElectives,workload:loadWorkload,
    leaves:loadLeaves,settings:loadSettings})[pg]?.();
}

// ═══ TOAST ═══════════════════════════════════════════════════════
let _tt2;
function toast(msg,type='ok'){
  const t=document.getElementById('toast');
  t.innerHTML={ok:'✓',err:'✕',info:'ℹ'}[type]+' '+msg;
  t.className='show '+type;clearTimeout(_tt2);_tt2=setTimeout(()=>t.className='',3000);
}

// ═══ API ══════════════════════════════════════════════════════════
async function api(path,method='GET',body=null){
  const opts={method,headers:{'Content-Type':'application/json'}};
  if(body) opts.body=JSON.stringify(body);
  const r=await fetch(path,opts);
  if(r.status===401){if(path!=='/api/login'){doLogout();}return null;}
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

// ═══ INIT ═════════════════════════════════════════════════════════
async function initApp(){
  const cfg=await api('/api/settings');if(!cfg)return;
  document.getElementById('sf-inst').textContent=cfg.institution||'—';
  document.getElementById('logo-sem').textContent=cfg.semester||'v3.0';
  if(cfg.theme==='light') document.documentElement.dataset.theme='light';
  await doGenerate(false,true);loadDash();
}

// ═══ THEME ════════════════════════════════════════════════════════
function toggleTheme(){
  const h=document.documentElement,next=h.dataset.theme==='dark'?'light':'dark';
  h.dataset.theme=next;api('/api/settings','POST',{theme:next});
  if(document.getElementById('page-analytics').classList.contains('active')) loadAnalytics();
}

// ═══ DASHBOARD ════════════════════════════════════════════════════
async function loadDash(){
  const [s,hist,cfg,rooms]=await Promise.all([api('/api/stats'),api('/api/history'),api('/api/settings'),api('/api/rooms')]);
  if(!s)return;
  document.getElementById('st-s').textContent=s.subjects;document.getElementById('st-f').textContent=s.faculty;
  document.getElementById('st-r').textContent=s.rooms;document.getElementById('st-b').textContent=s.batches;
  document.getElementById('st-c').textContent=s.classes_scheduled;document.getElementById('st-cf').textContent=s.conflicts;
  document.getElementById('st-fr').textContent=s.fill_rate+'%';document.getElementById('st-d').textContent=s.departments;
  const nb=document.getElementById('nb-cf');
  if(s.conflicts>0){nb.textContent=s.conflicts;nb.style.display='';}else nb.style.display='none';
  const nl=document.getElementById('nb-lv');
  if(s.leaves_pending>0){nl.textContent=s.leaves_pending;nl.style.display='';}else nl.style.display='none';
  document.getElementById('hero-inst').textContent=cfg.institution||'SmartSchedule';
  document.getElementById('hero-sem').textContent=cfg.semester||'Current Semester';
  document.getElementById('sf-inst').textContent=cfg.institution||'—';
  document.getElementById('logo-sem').textContent=cfg.semester||'v3.0';
  const rmap=Object.fromEntries((rooms||[]).map(r=>[r.id,r]));
  const tot=DAYS.length*SLOTS.length;
  document.getElementById('room-util').innerHTML=
    Object.entries(s.room_utilization||{}).sort((a,b)=>b[1]-a[1]).map(([rid,cnt])=>{
      const r=rmap[rid]||{};const pct=Math.round(cnt/tot*100);
      const col=pct>70?'var(--dn)':pct>40?'var(--wn)':'var(--ac2)';
      return `<div class="wr"><div class="wn2" title="${r.name||rid}">${r.name||rid}</div><div class="wt"><div class="wf" style="width:${pct}%;background:${col}"></div></div><div class="wlb">${cnt}h</div></div>`;
    }).join('')||'<p style="color:var(--mu);font-size:12px">Generate a timetable first.</p>';
  document.getElementById('gen-hist').innerHTML=(hist||[]).length
    ?(hist||[]).map(h=>`<div class="hrow"><div class="hts">${h.ts}</div><div class="hb"><span style="color:var(--ok)">✓ ${h.classes} classes</span>${h.conflicts>0?`<span style="color:var(--wn)"> · ⚠ ${h.conflicts}</span>`:''}<span style="color:var(--mu2);font-size:10px"> seed:${h.seed||'?'}</span></div></div>`).join('')
    :'<p style="color:var(--mu);font-size:12px">No history yet.</p>';
}

// ═══ GENERATE ══════════════════════════════════════════════════════
async function doGenerate(reload=false,quiet=false){
  if(!quiet) toast('Generating…','info');
  try{
    const body=lastSeed!==null?{seed:lastSeed}:{};
    const data=await api('/api/generate','POST',body);if(!data)return;
    ttData=data;lastSeed=data.seed;
    const n=data.conflicts.length;
    if(!quiet) toast(n>0?`⚠ Done — ${n} conflict(s)`:'✅ Generated!',n>0?'info':'ok');
    if(reload) loadTT();
    else if(!quiet) nav(document.querySelector('[data-page=timetable]'));
    loadDash();
  }catch(e){toast('Error: '+e.message,'err');}
}
function openSeedModal(){
  smo(`<h3>🎲 Custom Seed</h3>
    <p style="font-size:12px;color:var(--mu);margin-bottom:12px">Reproduce a specific schedule. Last: <b style="color:var(--ac)">${lastSeed??'none'}</b></p>
    <div class="fg"><label>Seed Number</label><input id="m-seed" type="number" placeholder="e.g. 42" value="${lastSeed||''}"></div>
    <div class="fa"><button class="btn bg" onclick="cmo()">Cancel</button><button class="btn bp" onclick="useSeed()">Generate</button></div>`);
}
async function useSeed(){lastSeed=parseInt(document.getElementById('m-seed').value)||null;cmo();await doGenerate(true);}

// ═══ TIMETABLE ══════════════════════════════════════════════════════
async function loadTT(){
  if(!ttData){const d=await api('/api/timetable');if(d)ttData=d;}
  await popEntitySel();renderCF(ttData.conflicts,ttData.suggestions||[]);renderTT();
}
async function onViewChange(){
  await popEntitySel();
  document.getElementById('tt-sel-lbl').textContent={batch:'Batch:',faculty:'Faculty:',room:'Room:'}[document.getElementById('tt-view').value];
  renderTT();
}
async function popEntitySel(){
  const view=document.getElementById('tt-view').value;
  const sel=document.getElementById('tt-entity');
  const items=await api({batch:'/api/batches',faculty:'/api/faculty',room:'/api/rooms'}[view]);
  if(!items)return;
  sel.innerHTML=items.map(x=>`<option value="${x.id}">${x.name}</option>`).join('');
}
function renderCF(cf,tips){
  const a=document.getElementById('tt-cf-area');
  if(!cf||!cf.length){a.innerHTML='';return;}
  a.innerHTML=`<div class="cpn"><div class="ch"><h4>⚠ Conflicts</h4><span>${cf.length} issue(s) — check Suggestions tab for fixes</span></div>
    <div class="ctabs"><div class="ctab active" onclick="ctSw(0,this)">Issues (${cf.length})</div><div class="ctab" onclick="ctSw(1,this)">AI Suggestions (${tips.length})</div></div>
    <ul class="cl" id="cl-i">${cf.map(c=>`<li>${c.msg||c}</li>`).join('')}</ul>
    <ul class="cl tips" id="cl-t" style="display:none">${tips.map(t=>`<li>${t}</li>`).join('')||'<li>No further suggestions.</li>'}</ul>
  </div>`;
}
function ctSw(i,el){
  document.querySelectorAll('.ctab').forEach(t=>t.classList.remove('active'));el.classList.add('active');
  document.getElementById('cl-i').style.display=i===0?'':'none';
  document.getElementById('cl-t').style.display=i===1?'':'none';
}
function renderTT(){
  if(!ttData)return;
  const view=document.getElementById('tt-view').value,eid=document.getElementById('tt-entity').value,tt=ttData.timetable;
  const grid={};DAYS.forEach(d=>{grid[d]={};SLOTS.forEach(s=>{grid[d][s]=null;});});
  if(view==='batch'){const b=tt[eid]||{};DAYS.forEach(d=>SLOTS.forEach(s=>{grid[d][s]=(b[d]&&b[d][s])||null;}));}
  else if(view==='faculty'){Object.values(tt).forEach(bd=>DAYS.forEach(d=>SLOTS.forEach(s=>{const e=bd[d]&&bd[d][s];if(e&&e.facultyId===eid)grid[d][s]=e;})));}
  else{Object.values(tt).forEach(bd=>DAYS.forEach(d=>SLOTS.forEach(s=>{const e=bd[d]&&bd[d][s];if(e&&e.roomId===eid)grid[d][s]=e;})));}
  let h=`<thead><tr><th>Slot</th>${DAYS.map(d=>`<th>${d}</th>`).join('')}</tr></thead><tbody>`;
  SLOTS.forEach(slot=>{
    h+=`<tr><td><span class="slbl">Period</span>${slot}</td>`;
    DAYS.forEach(day=>{
      const e=grid[day][slot];
      if(e){
        const lc=e.type==='lab'?'lb':'',ec=e.elective?'el':'',bid=e.batchId||eid;
        const ej=JSON.stringify(e).replace(/'/g,"&#39;").replace(/"/g,"&quot;");
        h+=`<td><div class="cc ${lc} ${ec}" draggable="true"
          ondragstart="dstart(event,'${bid}','${day}','${slot}')"
          ondragover="event.preventDefault();this.classList.add('dov')"
          ondragleave="this.classList.remove('dov')"
          ondrop="ddrop(event,'${bid}','${day}','${slot}')"
          onclick="showDet(${ej})">
          <button class="cdl" onclick="event.stopPropagation();clrSlot('${bid}','${day}','${slot}')">✕</button>
          <div class="cs">${e.subject}${e.elective?' <span class="badge be" style="font-size:8px">E</span>':''}</div>
          <div class="cm">📍 ${e.room}</div>
          <div class="cm">👤 ${e.faculty}</div>
          ${view!=='batch'?`<div class="cm">🎓 ${e.batch}</div>`:''}
        </div></td>`;
      }else{
        h+=`<td><div class="ce" ondragover="event.preventDefault();this.style.background='rgba(0,212,170,.07)'" ondragleave="this.style.background=''" ondrop="ddrop(event,'${view==='batch'?eid:''}','${day}','${slot}')">+</div></td>`;
      }
    });
    h+='</tr>';
  });
  document.getElementById('tt-tbl').innerHTML=h+'</tbody>';
}

// ── DRAG & DROP ──────────────────────────────────────
let _dr={};
function dstart(e,bid,day,slot){_dr={bid,day,slot};e.currentTarget.classList.add('dg2');e.dataTransfer.effectAllowed='move';}
async function ddrop(e,bid,day,slot){
  e.preventDefault();
  document.querySelectorAll('.cc').forEach(c=>c.classList.remove('dg2','dov'));
  document.querySelectorAll('.ce').forEach(c=>c.style.background='');
  if(_dr.bid===bid&&_dr.day===day&&_dr.slot===slot)return;
  await api('/api/timetable/swap','POST',{batchId:_dr.bid||bid,srcDay:_dr.day,srcSlot:_dr.slot,dstDay:day,dstSlot:slot});
  const d=await api('/api/timetable');if(d)ttData=d;
  renderTT();toast('Slots swapped ✓','ok');
}
function showDet(e){
  smo(`<h3>📖 Class Details</h3>
    <table style="width:100%;border-collapse:collapse">
      ${[['Subject',e.subject+(e.type?` <span class="badge ${e.type==='lab'?'bl':'bt'}">${e.type}</span>`:'')],
         ['Code',e.code||'—'],['Faculty',e.faculty],['Room',e.room],['Batch',e.batch],
         ['Elective',e.elective?'<span class="badge be">Yes</span>':'No']]
        .map(([k,v])=>`<tr><td style="padding:8px 0;font-size:10px;font-weight:700;color:var(--mu);width:74px;border-bottom:1px solid var(--brd)">${k}</td><td style="padding:8px 0;font-size:12.5px;border-bottom:1px solid var(--brd)">${v}</td></tr>`).join('')}
    </table>
    <div class="fa"><button class="btn bg" onclick="cmo()">Close</button></div>`);
}
async function clrSlot(bid,day,slot){
  if(!confirm('Clear this slot?'))return;
  await api('/api/timetable/edit','POST',{batchId:bid,day,slot,entry:null});
  if(ttData?.timetable?.[bid]?.[day])ttData.timetable[bid][day][slot]=null;
  toast('Cleared','ok');renderTT();
}
function exportCSV(){window.location='/api/timetable/export/csv?batchId='+document.getElementById('tt-entity').value;}
function archivePrompt(){
  smo(`<h3>📦 Archive Timetable</h3>
    <div class="fg"><label>Label</label><input id="m-albl" placeholder="e.g. Even Sem 2025 Final"></div>
    <div class="fa"><button class="btn bg" onclick="cmo()">Cancel</button><button class="btn bp" onclick="doArchive()">Save</button></div>`);
}
async function doArchive(){
  const lbl=document.getElementById('m-albl').value.trim()||'Archive '+new Date().toLocaleDateString();
  await api('/api/timetable/archive','POST',{label:lbl});cmo();toast('Archived!','ok');
}
async function openArchives(){
  const arcs=await api('/api/archives');
  if(!arcs||!arcs.length){toast('No archives yet','info');return;}
  smo(`<h3>🗂 Saved Archives</h3>
    <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px">
      ${arcs.map(a=>`<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--brd)">
        <div><div style="font-weight:600;font-size:12.5px">${a.label}</div><div style="font-size:10px;color:var(--mu)">${a.ts}</div></div>
        <button class="btn bg bsm" onclick="restoreArc('${a.id}')">↩ Restore</button>
      </div>`).join('')}
    </div>
    <div class="fa"><button class="btn bg" onclick="cmo()">Close</button></div>`);
}
async function restoreArc(id){
  if(!confirm('Restore this archive? Current timetable will be replaced.'))return;
  await api('/api/timetable/archive/'+id,'POST');
  const d=await api('/api/timetable');if(d)ttData=d;
  cmo();toast('Restored!','ok');renderTT();loadDash();
}

// ═══ ANALYTICS ══════════════════════════════════════════════════════
async function loadAnalytics(){
  const [s,facs,rooms,subjs]=await Promise.all([api('/api/stats'),api('/api/faculty'),api('/api/rooms'),api('/api/subjects')]);
  if(!s)return;
  const dark=document.documentElement.dataset.theme==='dark';
  const gc=dark?'rgba(255,255,255,.07)':'rgba(0,0,0,.07)',tc=dark?'#607090':'#607090';
  Chart.defaults.color=tc;
  const fmap=Object.fromEntries((facs||[]).map(f=>[f.id,f.name]));
  const rmap=Object.fromEntries((rooms||[]).map(r=>[r.id,r.name]));
  const smap=Object.fromEntries((subjs||[]).map(x=>[x.id,x.name]));
  const C=['#4f8ef7','#00d4aa','#f7914f','#c97af5','#f74f6a','#f7c24f','#3ecf8e','#9b6bf7'];
  function mk(id,type,labels,datasets){
    if(_charts[id])_charts[id].destroy();
    _charts[id]=new Chart(document.getElementById(id).getContext('2d'),{type,data:{labels,datasets},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:type!=='bar',labels:{color:tc,font:{size:10}}}},
        scales:type==='bar'?{x:{grid:{color:gc},ticks:{color:tc}},y:{grid:{color:gc},ticks:{color:tc}}}:{}}});
  }
  const dd=s.day_distribution||{};mk('ch-day','bar',DAYS,[{data:DAYS.map(d=>dd[d]||0),backgroundColor:DAYS.map((_,i)=>C[i%C.length]),borderRadius:5}]);
  const fw=s.faculty_workload||{};mk('ch-fac','bar',Object.keys(fw).map(id=>fmap[id]||id),[{data:Object.values(fw),backgroundColor:Object.keys(fw).map((_,i)=>C[i%C.length]),borderRadius:5}]);
  const ru=s.room_utilization||{};mk('ch-room','doughnut',Object.keys(ru).map(id=>rmap[id]||id),[{data:Object.values(ru),backgroundColor:Object.keys(ru).map((_,i)=>C[i%C.length]),borderWidth:0}]);
  const sc=s.subject_count||{};mk('ch-subj','doughnut',Object.keys(sc).map(id=>smap[id]||id),[{data:Object.values(sc),backgroundColor:Object.keys(sc).map((_,i)=>C[i%C.length]),borderWidth:0}]);
}

// ═══ NOTICES ════════════════════════════════════════════════════════
async function loadNotices(){
  const items=await api('/api/notices');if(!items)return;
  const g=document.getElementById('notices-list');
  if(!items.length){g.innerHTML=emp('📢','No notices posted.');return;}
  g.innerHTML=items.map(n=>`<div class="nc ${n.priority||'normal'}">
    <div class="nc-hd"><div class="nc-ti">${n.title}</div>
      ${me?.role==='admin'?`<button class="btn bd bsm" onclick="del('notices','${n.id}',loadNotices)">🗑</button>`:''}
    </div>
    <div class="nc-mt">By ${n.author} · ${n.date} · <span class="badge ${n.priority==='high'?'bd2':'bav'}">${n.priority||'normal'}</span></div>
    <div class="nc-bd">${n.body}</div>
  </div>`).join('');
}

// ═══ AI CHAT ════════════════════════════════════════════════════════
async function sendChat(){
  const inp=document.getElementById('chat-in'),msg=inp.value.trim();if(!msg)return;
  inp.value='';addBub('user',msg);
  const typ=document.createElement('div');typ.className='chat-typing';typ.textContent='AI is thinking…';
  document.getElementById('chat-msgs').appendChild(typ);scrollChat();
  try{
    const r=await api('/api/chat','POST',{message:msg});typ.remove();
    if(r) addBub('ai',r.response);
  }catch(e){typ.remove();addBub('ai','⚠ Error: '+e.message);}
}
function qa(msg){document.getElementById('chat-in').value=msg;sendChat();}
function addBub(role,msg){
  const d=document.createElement('div');d.className='cb '+role;
  const fmt=msg.replace(/[*][*](.*?)[*][*]/g,'<b>$1</b>').split(String.fromCharCode(10)).join('<br>');
  const ts=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  d.innerHTML=fmt+`<div class="ts">${ts}</div>`;
  document.getElementById('chat-msgs').appendChild(d);scrollChat();
}
function scrollChat(){const m=document.getElementById('chat-msgs');m.scrollTop=m.scrollHeight;}
function clearChat(){document.getElementById('chat-msgs').innerHTML='<div class="cb ai">Chat cleared. Ask me anything!<div class="ts">Now</div></div>';}

// ═══ SUBJECTS ════════════════════════════════════════════════════════
async function loadSubjects(){
  const [items,depts]=await Promise.all([api('/api/subjects'),api('/api/departments')]);if(!items)return;
  const dmap=Object.fromEntries((depts||[]).map(d=>[d.id,d.code]));
  const g=document.getElementById('subj-grid');
  if(!items.length){g.innerHTML=emp('📚','No subjects yet.');return;}
  g.innerHTML=items.map(s=>`<div class="dc" data-search="${s.name.toLowerCase()}">
    <div class="dch"><div class="dct">📚 ${s.name}</div><span class="dcid">${s.id}</span></div>
    <div class="dctg"><span class="badge ${s.type==='lab'?'bl':'bt'}">${s.type}</span><span class="badge bav">${s.hours}h/wk</span>
      ${s.elective?'<span class="badge be">Elective</span>':''}${s.code?`<span class="badge bday">${s.code}</span>`:''}
      ${s.deptId?`<span class="badge bday">${dmap[s.deptId]||s.deptId}</span>`:''}
    </div>
    <div class="dca"><button class="btn bg bsm" onclick="openModal('subject',${esc(s)})">✏ Edit</button>
      <button class="btn bd bsm" onclick="del('subjects','${s.id}',loadSubjects)">🗑</button></div>
  </div>`).join('');
}

// ═══ FACULTY ════════════════════════════════════════════════════════
async function loadFaculty(){
  const [fac,subjs,depts]=await Promise.all([api('/api/faculty'),api('/api/subjects'),api('/api/departments')]);if(!fac)return;
  const smap=Object.fromEntries((subjs||[]).map(s=>[s.id,s.name])),dmap=Object.fromEntries((depts||[]).map(d=>[d.id,d.code]));
  const g=document.getElementById('fac-grid');
  if(!fac.length){g.innerHTML=emp('👨‍🏫','No faculty yet.');return;}
  g.innerHTML=fac.map(f=>`<div class="dc" data-search="${f.name.toLowerCase()}">
    <div class="dch"><div class="dct">👨‍🏫 ${f.name}</div><span class="dcid">${f.id}</span></div>
    <div class="dcs">${f.email||''} ${f.deptId?`· <span class="badge bday">${dmap[f.deptId]||''}</span>`:''}</div>
    <div class="dcs">Max: ${f.max_hours||20}h/week</div>
    <div class="dctg">${f.availability.map(d=>`<span class="badge bday">${d}</span>`).join('')}</div>
    <div class="dcs">Subjects: ${f.subjects.map(id=>smap[id]||id).join(', ')||'None'}</div>
    <div class="dca"><button class="btn bg bsm" onclick="openModal('faculty',${esc(f)})">✏ Edit</button>
      <button class="btn bd bsm" onclick="del('faculty','${f.id}',loadFaculty)">🗑</button></div>
  </div>`).join('');
}

// ═══ ROOMS ════════════════════════════════════════════════════════
async function loadRooms(){
  const items=await api('/api/rooms');if(!items)return;
  const g=document.getElementById('room-grid');
  if(!items.length){g.innerHTML=emp('🏫','No rooms yet.');return;}
  g.innerHTML=items.map(r=>`<div class="dc" data-search="${r.name.toLowerCase()}">
    <div class="dch"><div class="dct">🏫 ${r.name}</div><span class="dcid">${r.id}</span></div>
    <div class="dctg"><span class="badge ${r.type==='lab'?'bl':'bt'}">${r.type}</span><span class="badge bav">Cap: ${r.capacity}</span>
      ${r.building?`<span class="badge bday">${r.building} F${r.floor||'?'}</span>`:''}
    </div>
    <div class="dca"><button class="btn bg bsm" onclick="openModal('room',${esc(r)})">✏ Edit</button>
      <button class="btn bd bsm" onclick="del('rooms','${r.id}',loadRooms)">🗑</button></div>
  </div>`).join('');
}

// ═══ BATCHES ════════════════════════════════════════════════════════
async function loadBatches(){
  const [items,depts]=await Promise.all([api('/api/batches'),api('/api/departments')]);if(!items)return;
  const dmap=Object.fromEntries((depts||[]).map(d=>[d.id,d.name]));
  const g=document.getElementById('bat-grid');
  if(!items.length){g.innerHTML=emp('👥','No batches yet.');return;}
  g.innerHTML=items.map(b=>`<div class="dc" data-search="${b.name.toLowerCase()}">
    <div class="dch"><div class="dct">👥 ${b.name}</div><span class="dcid">${b.id}</span></div>
    <div class="dctg"><span class="badge bav">Strength: ${b.strength}</span>
      ${b.year?`<span class="badge bday">Year ${b.year}</span>`:''}
      ${b.deptId?`<span class="badge bday">${dmap[b.deptId]||b.deptId}</span>`:''}
    </div>
    <div class="dca"><button class="btn bg bsm" onclick="openModal('batch',${esc(b)})">✏ Edit</button>
      <button class="btn bd bsm" onclick="del('batches','${b.id}',loadBatches)">🗑</button></div>
  </div>`).join('');
}

// ═══ ELECTIVES ════════════════════════════════════════════════════
async function loadElectives(){
  const [groups,subjs,batches]=await Promise.all([api('/api/elective_groups'),api('/api/subjects'),api('/api/batches')]);if(!groups)return;
  const smap=Object.fromEntries((subjs||[]).map(s=>[s.id,s.name])),bmap=Object.fromEntries((batches||[]).map(b=>[b.id,b.name]));
  const g=document.getElementById('elec-grid');
  if(!groups.length){g.innerHTML=emp('📘','No elective groups. Add elective subjects first.');return;}
  g.innerHTML=groups.map(eg=>`<div class="dc">
    <div class="dch"><div class="dct">📘 ${eg.name}</div><span class="dcid">${eg.id}</span></div>
    <div class="dcs">Subjects: ${eg.subjects.map(id=>smap[id]||id).join(', ')||'None'}</div>
    <div class="dcs">Batches: ${eg.batches.map(id=>bmap[id]||id).join(', ')||'None'}</div>
    <div class="dca"><button class="btn bd bsm" onclick="del('elective_groups','${eg.id}',loadElectives)">🗑 Delete</button></div>
  </div>`).join('');
}

// ═══ WORKLOAD ════════════════════════════════════════════════════
async function loadWorkload(){
  const rep=await api('/api/report/faculty');if(!rep)return;
  document.getElementById('wl-bars').innerHTML=rep.map(r=>{
    const pct=Math.round(r.total_hours/Math.max(r.max_hours,1)*100),over=r.total_hours>r.max_hours;
    const col=over?'var(--dn)':pct>75?'var(--wn)':'var(--ok)';
    return `<div class="wr"><div class="wn2" title="${r.name}">${r.name}</div><div class="wt"><div class="wf" style="width:${Math.min(pct,100)}%;background:${col}"></div></div><div class="wlb ${over?'wov':''}">${r.total_hours}/${r.max_hours}h</div></div>`;
  }).join('');
  document.getElementById('wl-tabs').innerHTML=rep.map((r,i)=>`<div class="tab ${i===0?'active':''}" onclick="wlTab(${i},this)">${r.name.split(' ').slice(-1)[0]}</div>`).join('');
  window._wlr=rep;wlShow(0);
}
function wlTab(i,el){document.querySelectorAll('#wl-tabs .tab').forEach(t=>t.classList.remove('active'));el.classList.add('active');wlShow(i);}
function wlShow(i){
  const r=window._wlr?.[i];if(!r)return;
  const d=document.getElementById('wl-det');
  if(!r.schedule.length){d.innerHTML='<p style="color:var(--mu);font-size:12px">No classes scheduled.</p>';return;}
  d.innerHTML=`<p style="font-size:12px;color:var(--mu);margin-bottom:9px">${r.name} · ${r.email||'—'} · <b style="color:var(--tx)">${r.total_hours}</b>/${r.max_hours}h ${r.total_hours>r.max_hours?'<span class="badge bd2" style="margin-left:5px">Overloaded</span>':''}</p>
    <table class="mt"><thead><tr><th>Day</th><th>Slot</th><th>Subject</th><th>Room</th><th>Batch</th></tr></thead>
    <tbody>${r.schedule.map(s=>`<tr><td>${s.day}</td><td>${s.slot}</td><td>${s.subject}</td><td>${s.room}</td><td>${s.batch}</td></tr>`).join('')}</tbody></table>`;
}

// ═══ LEAVES ═════════════════════════════════════════════════════
async function loadLeaves(){
  const [leaves,subs,fac]=await Promise.all([api('/api/leaves'),api('/api/substitutions'),api('/api/faculty')]);
  window._lv=leaves||[];window._sub=subs||[];window._fac=fac||[];renderLeaves();
}
function renderLeaves(){
  const p=document.getElementById('lv-panel'),lv=window._lv||[];
  if(!lv.length){p.innerHTML=emp('🏖','No leave requests.');return;}
  p.innerHTML=lv.map(l=>`<div class="lvc">
    <div class="lvi"><div class="lv-nm">${l.facultyName||l.facultyId||'Faculty'}</div><div class="lv-mt">${l.date||'—'} · ${l.reason||'No reason'}</div></div>
    <span class="sbadge ${l.status==='approved'?'sa':'sp'}">${l.status}</span>
    <div style="display:flex;gap:6px">
      ${l.status==='pending'&&me?.role==='admin'?`<button class="btn bs bsm" onclick="approveLv('${l.id}')">✓ Approve</button>`:''}
      <button class="btn bd bsm" onclick="del('leaves','${l.id}',loadLeaves)">🗑</button>
    </div>
  </div>`).join('');
}
async function approveLv(id){await api('/api/leaves/'+id+'/approve','POST');toast('Approved','ok');loadLeaves();}
function lvTab(i,el){
  document.querySelectorAll('#page-leaves .tab').forEach(t=>t.classList.remove('active'));el.classList.add('active');
  document.getElementById('lv-panel').style.display=i===0?'':'none';
  document.getElementById('sub-panel').style.display=i===1?'':'none';
  if(i===1) renderSubs();
}
function renderSubs(){
  const subs=window._sub||[],p=document.getElementById('sub-panel');
  if(!subs.length){p.innerHTML=emp('🔄','No substitutions scheduled.');return;}
  p.innerHTML=`<table class="mt"><thead><tr><th>Date</th><th>Original</th><th>Substitute</th><th>Slot</th><th></th></tr></thead>
    <tbody>${subs.map(s=>`<tr><td>${s.date||'—'}</td><td>${s.original||'—'}</td><td>${s.substitute||'—'}</td><td>${s.slot||'—'}</td>
      <td><button class="btn bd bsm" onclick="del('substitutions','${s.id}',loadLeaves)">🗑</button></td></tr>`).join('')}</tbody></table>`;
}

// ═══ SETTINGS ════════════════════════════════════════════════════
async function loadSettings(){
  const s=await api('/api/settings');if(!s)return;
  document.getElementById('set-inst').value=s.institution||'';
  document.getElementById('set-sem').value=s.semester||'';
  document.getElementById('set-dur').value=s.slot_duration||60;
}
async function saveSettings(){
  await api('/api/settings','POST',{institution:document.getElementById('set-inst').value.trim(),semester:document.getElementById('set-sem').value.trim(),slot_duration:parseInt(document.getElementById('set-dur').value)});
  toast('Saved','ok');initApp();
}

// ═══ MODALS ══════════════════════════════════════════════════════
async function openModal(type,ex=null){
  const isE=!!ex;
  if(type==='subject'){
    const depts=await api('/api/departments');
    smo(`<h3>${isE?'✏ Edit':'+ Add'} Subject</h3>
      <div class="frow"><div class="fg"><label>Name</label><input id="m-name" value="${ex?.name||''}"></div><div class="fg"><label>Code</label><input id="m-code" value="${ex?.code||''}" placeholder="e.g. CS101"></div></div>
      <div class="frow">
        <div class="fg"><label>Type</label><select id="m-type"><option value="theory" ${(ex?.type||'theory')==='theory'?'selected':''}>Theory</option><option value="lab" ${ex?.type==='lab'?'selected':''}>Lab</option></select></div>
        <div class="fg"><label>Hours/Week</label><input id="m-hours" type="number" min="1" max="10" value="${ex?.hours||3}"></div>
      </div>
      <div class="frow">
        <div class="fg"><label>Department</label><select id="m-dept">${(depts||[]).map(d=>`<option value="${d.id}" ${ex?.deptId===d.id?'selected':''}>${d.name}</option>`).join('')}</select></div>
        <div class="fg"><label>Elective?</label><select id="m-elec"><option value="false" ${!ex?.elective?'selected':''}>No</option><option value="true" ${ex?.elective?'selected':''}>Yes</option></select></div>
      </div>
      <div class="fa"><button class="btn bg" onclick="cmo()">Cancel</button><button class="btn bp" onclick="saveSub(${isE?`'${ex.id}'`:'null'})">${isE?'Save':'Add'}</button></div>`);
  }else if(type==='faculty'){
    const [subjs,depts]=await Promise.all([api('/api/subjects'),api('/api/departments')]);
    const av=ex?.availability||ALLD,ss=ex?.subjects||[];
    smo(`<h3>${isE?'✏ Edit':'+ Add'} Faculty</h3>
      <div class="frow"><div class="fg"><label>Full Name</label><input id="m-name" value="${ex?.name||''}"></div><div class="fg"><label>Max Hours/Week</label><input id="m-maxh" type="number" min="1" max="40" value="${ex?.max_hours||20}"></div></div>
      <div class="frow"><div class="fg"><label>Email</label><input id="m-email" type="email" value="${ex?.email||''}" placeholder="name@college.edu"></div><div class="fg"><label>Department</label><select id="m-dept">${(depts||[]).map(d=>`<option value="${d.id}" ${ex?.deptId===d.id?'selected':''}>${d.name}</option>`).join('')}</select></div></div>
      <div class="fg"><label>Available Days</label><div class="dchips">${ALLD.map(d=>`<span class="dchip ${av.includes(d)?'on':''}" onclick="this.classList.toggle('on')" data-day="${d}">${d}</span>`).join('')}</div></div>
      <div class="fg"><label>Assigned Subjects</label><div style="display:flex;flex-direction:column;gap:5px;max-height:115px;overflow-y:auto;margin-top:2px">
        ${(subjs||[]).map(s=>`<label style="display:flex;align-items:center;gap:7px;font-size:12px;cursor:pointer"><input type="checkbox" class="sc" value="${s.id}" ${ss.includes(s.id)?'checked':''}> ${s.name} <span class="badge ${s.type==='lab'?'bl':'bt'}" style="font-size:9px">${s.type}</span></label>`).join('')}
      </div></div>
      <div class="fa"><button class="btn bg" onclick="cmo()">Cancel</button><button class="btn bp" onclick="saveFac(${isE?`'${ex.id}'`:'null'})">${isE?'Save':'Add'}</button></div>`);
  }else if(type==='room'){
    smo(`<h3>${isE?'✏ Edit':'+ Add'} Room</h3>
      <div class="frow"><div class="fg"><label>Name</label><input id="m-name" value="${ex?.name||''}"></div><div class="fg"><label>Building</label><input id="m-bld" value="${ex?.building||''}" placeholder="e.g. Main Block"></div></div>
      <div class="frow"><div class="fg"><label>Type</label><select id="m-type"><option value="theory" ${(ex?.type||'theory')==='theory'?'selected':''}>Theory</option><option value="lab" ${ex?.type==='lab'?'selected':''}>Lab</option></select></div><div class="fg"><label>Capacity</label><input id="m-cap" type="number" min="1" value="${ex?.capacity||60}"></div></div>
      <div class="fa"><button class="btn bg" onclick="cmo()">Cancel</button><button class="btn bp" onclick="saveRoom(${isE?`'${ex.id}'`:'null'})">${isE?'Save':'Add'}</button></div>`);
  }else if(type==='batch'){
    const depts=await api('/api/departments');
    smo(`<h3>${isE?'✏ Edit':'+ Add'} Batch</h3>
      <div class="frow"><div class="fg"><label>Batch Name</label><input id="m-name" value="${ex?.name||''}"></div><div class="fg"><label>Strength</label><input id="m-str" type="number" min="1" value="${ex?.strength||50}"></div></div>
      <div class="frow"><div class="fg"><label>Year</label><input id="m-year" type="number" min="1" max="4" value="${ex?.year||1}"></div><div class="fg"><label>Department</label><select id="m-dept">${(depts||[]).map(d=>`<option value="${d.id}" ${ex?.deptId===d.id?'selected':''}>${d.name}</option>`).join('')}</select></div></div>
      <div class="fa"><button class="btn bg" onclick="cmo()">Cancel</button><button class="btn bp" onclick="saveBatch(${isE?`'${ex.id}'`:'null'})">${isE?'Save':'Add'}</button></div>`);
  }else if(type==='notice'){
    smo(`<h3>📢 Post Notice</h3>
      <div class="fg"><label>Title</label><input id="m-title" placeholder="Notice title"></div>
      <div class="fg"><label>Body</label><textarea id="m-body" rows="3" placeholder="Notice content…"></textarea></div>
      <div class="fg"><label>Priority</label><select id="m-pri"><option value="normal">Normal</option><option value="high">High</option></select></div>
      <div class="fa"><button class="btn bg" onclick="cmo()">Cancel</button><button class="btn bp" onclick="saveNotice()">Post</button></div>`);
  }else if(type==='leave'){
    const fac=await api('/api/faculty');
    smo(`<h3>🏖 Apply Leave</h3>
      <div class="fg"><label>Faculty</label><select id="m-fac">${(fac||[]).map(f=>`<option value="${f.id}|${f.name}">${f.name}</option>`).join('')}</select></div>
      <div class="fg"><label>Date</label><input id="m-date" type="date" value="${new Date().toISOString().split('T')[0]}"></div>
      <div class="fg"><label>Reason</label><input id="m-reason" placeholder="e.g. Medical leave"></div>
      <div class="fa"><button class="btn bg" onclick="cmo()">Cancel</button><button class="btn bp" onclick="saveLeave()">Submit</button></div>`);
  }else if(type==='elective'){
    const [subjs,batches]=await Promise.all([api('/api/subjects'),api('/api/batches')]);
    const elSubs=(subjs||[]).filter(s=>s.elective);
    smo(`<h3>📘 Add Elective Group</h3>
      <div class="fg"><label>Group Name</label><input id="m-name" placeholder="e.g. Open Elective I"></div>
      <div class="fg"><label>Elective Subjects</label><div style="display:flex;flex-direction:column;gap:5px;max-height:110px;overflow-y:auto;margin-top:2px">
        ${elSubs.map(s=>`<label style="display:flex;align-items:center;gap:7px;font-size:12px;cursor:pointer"><input type="checkbox" class="eg-sc" value="${s.id}"> ${s.name}</label>`).join('')}
        ${!elSubs.length?'<p style="color:var(--mu);font-size:11px">No elective subjects yet. Mark subjects as elective first.</p>':''}
      </div></div>
      <div class="fg"><label>Assign Batches</label><div style="display:flex;flex-direction:column;gap:5px;max-height:100px;overflow-y:auto;margin-top:2px">
        ${(batches||[]).map(b=>`<label style="display:flex;align-items:center;gap:7px;font-size:12px;cursor:pointer"><input type="checkbox" class="eg-bc" value="${b.id}"> ${b.name}</label>`).join('')}
      </div></div>
      <div class="fa"><button class="btn bg" onclick="cmo()">Cancel</button><button class="btn bp" onclick="saveElective()">Add Group</button></div>`);
  }
}

async function saveSub(id){
  const name=gv('m-name');if(!name){toast('Name required','err');return;}
  await api('/api/subjects',id?'PUT':'POST',{name,code:gv('m-code'),type:gv('m-type','s'),hours:parseInt(gv('m-hours'))||1,deptId:gv('m-dept','s'),elective:gv('m-elec','s')==='true',...(id?{id}:{})});
  cmo();toast(id?'Updated':'Added','ok');loadSubjects();
}
async function saveFac(id){
  const name=gv('m-name');if(!name){toast('Name required','err');return;}
  const days=[...document.querySelectorAll('.dchip.on')].map(c=>c.dataset.day);
  const subs=[...document.querySelectorAll('.sc:checked')].map(c=>c.value);
  await api('/api/faculty',id?'PUT':'POST',{name,email:gv('m-email'),max_hours:parseInt(gv('m-maxh'))||20,deptId:gv('m-dept','s'),availability:days,subjects:subs,...(id?{id}:{})});
  cmo();toast(id?'Updated':'Added','ok');loadFaculty();
}
async function saveRoom(id){
  const name=gv('m-name');if(!name){toast('Name required','err');return;}
  await api('/api/rooms',id?'PUT':'POST',{name,building:gv('m-bld'),type:gv('m-type','s'),capacity:parseInt(gv('m-cap'))||1,...(id?{id}:{})});
  cmo();toast(id?'Updated':'Added','ok');loadRooms();
}
async function saveBatch(id){
  const name=gv('m-name');if(!name){toast('Name required','err');return;}
  await api('/api/batches',id?'PUT':'POST',{name,strength:parseInt(gv('m-str'))||1,year:parseInt(gv('m-year'))||1,deptId:gv('m-dept','s'),...(id?{id}:{})});
  cmo();toast(id?'Updated':'Added','ok');loadBatches();
}
async function saveNotice(){
  const title=gv('m-title');if(!title){toast('Title required','err');return;}
  await api('/api/notices','POST',{title,body:gv('m-body'),author:me?.name||'Admin',priority:gv('m-pri','s')});
  cmo();toast('Posted','ok');loadNotices();
}
async function saveLeave(){
  const fv=gv('m-fac','s');const[fid,fname]=fv.split('|');
  await api('/api/leaves','POST',{facultyId:fid,facultyName:fname,date:gv('m-date'),reason:gv('m-reason')});
  cmo();toast('Submitted','ok');loadLeaves();
}
async function saveElective(){
  const name=gv('m-name');if(!name){toast('Name required','err');return;}
  const subs=[...document.querySelectorAll('.eg-sc:checked')].map(c=>c.value);
  const bats=[...document.querySelectorAll('.eg-bc:checked')].map(c=>c.value);
  await api('/api/elective_groups','POST',{name,subjects:subs,batches:bats});
  cmo();toast('Added','ok');loadElectives();
}

// ═══ HELPERS ═════════════════════════════════════════════════════
async function del(ep,id,reload){if(!confirm('Delete this item?'))return;await api('/api/'+ep,'DELETE',{id});toast('Deleted','ok');reload();}
function fc(gid,q){const q2=q.toLowerCase();document.querySelectorAll('#'+gid+' .dc').forEach(c=>{c.style.display=(c.dataset.search||c.textContent.toLowerCase()).includes(q2)?'':'none';});}
function smo(html){document.getElementById('mbox').innerHTML=html;document.getElementById('mo').classList.add('open');}
function cmo(e){if(e&&e.target!==document.getElementById('mo'))return;document.getElementById('mo').classList.remove('open');}
function emp(icon,msg){return`<div class="empty"><div class="ei">${icon}</div><p>${msg}</p></div>`;}
function esc(obj){return JSON.stringify(obj).replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function gv(id,t='i'){const el=document.getElementById(id);return el?el.value:'';}
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(FRONTEND)

if __name__ == "__main__":
    generate_timetable(seed=42)
    print("\n  +==========================================+")
    print("  |  Smart Classroom & Timetable Scheduler  |")
    print("  |  v3.0  -  Complete Edition              |")
    print("  +==========================================+")
    print("  |  Admin:   admin   /  admin123            |")
    print("  |  Faculty: sharma  /  sharma123           |")
    print("  |  Faculty: kapoor  /  kapoor123           |")
    print("  +==========================================+")
    print("  Open: http://localhost:5000\n")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
