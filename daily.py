#!/usr/bin/env python3
"""Daily posting helper for the cloud scheduled task.  PE_ENV or environment variables hold the keys.
  daily.py status                      buffer counts
  daily.py next                        pick today's carousel + a Reel of a different species; write previews to ./today/
  daily.py music "<query>"             licensed tracks from Instagram's library
  daily.py recut <slug> <bpm>          re-cut that post's Reel to a tempo (cuts on bar lines) and replace it
  daily.py carousel <slug> [caption_file]   publish the carousel
  daily.py reel <slug> <audio_id> [caption_file] [audio_label]   publish the Reel with that track
  daily.py theme <species words> [caption_file]  publish a theme-day carousel (best slide of up to 10 posts)
  daily.py approve carousel <slug> <YYYY-MM-DD> [caption_file]            approved for that day (8:00 am)
  daily.py approve reel <slug> <YYYY-MM-DD> <audio_id> "<label>" [caption_file]  approved for that day (8:30 pm)
  daily.py due carousel|reel           publish what was approved for today (or earlier and still unposted)
  daily.py skip <slug> carousel|reel   mark skipped
  daily.py redo <slug> "<note>"        put on the redo list for the next batch evening (Mac)
"""
import datetime as dt, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_cloud as pc

THEME_DAYS = {"03-03": ("World Wildlife Day", None), "08-10": ("World Lion Day", "lion"),
              "08-12": ("World Elephant Day", "elephant"), "09-22": ("World Rhino Day", "rhino"),
              "07-29": ("International Tiger Day", "tiger"), "12-04": ("International Cheetah Day", "cheetah"),
              "05-20": ("World Bee Day", "bee"), "08-19": ("World Photography Day", None)}

def state(): return pc.get_json("state/posts.json", {"posts": []})
def save(st): pc.put_json("state/posts.json", st)
def find(st, slug): return next(p for p in st["posts"] if p["slug"] == slug)
def cap_from(arg, default):
    return open(arg).read().strip() if arg and os.path.exists(arg) else default
from zoneinfo import ZoneInfo
def now_pt(): return dt.datetime.now(ZoneInfo("America/Vancouver")).replace(tzinfo=None)

cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
st = state()
if cmd == "status":
    c = [p for p in st["posts"] if p.get("schedule", True) and p["carousel"] == "pending"]
    r = [p for p in st["posts"] if p.get("schedule", True) and p.get("reel_status") == "pending"]
    print(json.dumps({"carousels_waiting": len(c), "reels_waiting": len(r),
                      "redo": [p["slug"] for p in st["posts"] if p.get("redo")],
                      "theme_today": THEME_DAYS.get(now_pt().strftime("%m-%d"))}, indent=1))
elif cmd == "next":
    os.makedirs("today", exist_ok=True)
    c = [p for p in st["posts"] if p.get("schedule", True) and p["carousel"] == "pending" and not p.get("redo")]
    car = c[0] if c else None
    sp = (car or {}).get("species", "") or ""
    base = lambda s: (s or "").lower().split("(")[0].strip()
    r = [p for p in st["posts"] if p.get("schedule", True) and p.get("reel_status") == "pending" and not p.get("redo")
         and (not car or (p["slug"] != car["slug"] and base(p.get("species")) != base(sp)))]
    reel = r[0] if r else None
    out = {"theme_today": THEME_DAYS.get(now_pt().strftime("%m-%d")), "carousel": None, "reel": None}
    if car:
        files = []
        for k in car["slides"]:
            f = "today/" + os.path.basename(k); pc.get_file(k, f); files.append(f)
        out["carousel"] = {"slug": car["slug"], "species": car.get("species"), "location": car.get("location"),
                           "caption": car["caption"], "slides": files}
    if reel:
        pc.get_file(reel["reel"], "today/reel.mp4")
        out["reel"] = {"slug": reel["slug"], "species": reel.get("species"), "caption": reel.get("reel_caption") or reel["caption"],
                       "file": "today/reel.mp4"}
    json.dump(out, open("today/today.json", "w"), indent=1); print(json.dumps(out, indent=1))
elif cmd == "music":
    for a in pc.find_music(sys.argv[2] if len(sys.argv) > 2 else None)[:12]:
        print(a["audio_id"], "|", a["title"], "|", a["display_artist"], "|", a["duration_in_ms"] // 1000, "s")
elif cmd == "recut":
    slug, bpm = sys.argv[2], sys.argv[3]
    d = f"src/{slug}"; os.makedirs(d + "/contest", exist_ok=True)
    keys = [o["Key"] for o in pc.r2().list_objects_v2(Bucket=pc.BUCKET, Prefix=f"posts/{slug}/src/").get("Contents", [])]
    for k in keys:
        n = os.path.basename(k); pc.get_file(k, f"{d}/plan.json" if n == "plan.json" else f"{d}/contest/{n}")
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists("logo.png"): pc.get_file("code/logo.png", "logo.png")
    subprocess.run([sys.executable, f"{here}/reel.py", d, "today/reel.mp4", "logo.png", bpm], check=True)
    pc.put_file("today/reel.mp4", find(st, slug)["reel"], "video/mp4"); print("re-cut at", bpm, "bpm")
elif cmd == "carousel":
    p = find(st, sys.argv[2]); cap = cap_from(sys.argv[3] if len(sys.argv) > 3 else None, p["caption"])
    mid = pc.publish_carousel([pc.link(k) for k in p["slides"]], cap)
    p.update(caption=cap, carousel="posted", carousel_media_id=mid, carousel_link=pc.permalink(mid),
             carousel_posted=dt.datetime.utcnow().isoformat()); save(st); print(p["carousel_link"])
elif cmd == "reel":
    p = find(st, sys.argv[2]); cap = cap_from(sys.argv[4] if len(sys.argv) > 4 else None, p.get("reel_caption") or p["caption"])
    mid = pc.publish_reel(pc.link(p["reel"]), cap, audio_id=sys.argv[3])
    p.update(reel_caption=cap, reel_status="posted", reel_media_id=mid, reel_link=pc.permalink(mid),
             reel_audio=sys.argv[5] if len(sys.argv) > 5 else sys.argv[3], reel_posted=dt.datetime.utcnow().isoformat())
    save(st); print(p["reel_link"])
elif cmd == "theme":
    words = sys.argv[2].lower()
    ps = [p for p in st["posts"] if p.get("schedule", True) and words in (p.get("species") or "").lower()][:10]
    if len(ps) < 2: sys.exit(f"only {len(ps)} posts of {words}")
    cap = cap_from(sys.argv[3] if len(sys.argv) > 3 else None, "")
    mid = pc.publish_carousel([pc.link(p["slides"][0]) for p in ps], cap)
    st.setdefault("themes", []).append({"date": now_pt().date().isoformat(), "species": words, "media_id": mid})
    save(st); print(pc.permalink(mid))
elif cmd == "approve":
    kind, slug, day = sys.argv[2], sys.argv[3], sys.argv[4]
    p = find(st, slug)
    if kind == "carousel":
        p.update(carousel="approved", carousel_date=day, caption=cap_from(sys.argv[5] if len(sys.argv) > 5 else None, p["caption"]))
    else:
        p.update(reel_status="approved", reel_date=day, reel_audio_id=sys.argv[5], reel_audio=sys.argv[6],
                 reel_caption=cap_from(sys.argv[7] if len(sys.argv) > 7 else None, p.get("reel_caption") or p["caption"]))
    save(st); print("approved", kind, slug, "for", day)
elif cmd == "due":
    kind, today = sys.argv[2], now_pt().date().isoformat()
    for p in st["posts"]:
        if kind == "carousel" and p.get("carousel") == "approved" and p.get("carousel_date", "9") <= today:
            mid = pc.publish_carousel([pc.link(k) for k in p["slides"]], p["caption"])
            p.update(carousel="posted", carousel_media_id=mid, carousel_link=pc.permalink(mid),
                     carousel_posted=dt.datetime.utcnow().isoformat()); save(st)
            print("POSTED carousel", p.get("species"), p["carousel_link"])
        if kind == "reel" and p.get("reel_status") == "approved" and p.get("reel_date", "9") <= today:
            mid = pc.publish_reel(pc.link(p["reel"]), p.get("reel_caption") or p["caption"], audio_id=p["reel_audio_id"])
            p.update(reel_status="posted", reel_media_id=mid, reel_link=pc.permalink(mid),
                     reel_posted=dt.datetime.utcnow().isoformat()); save(st)
            print("POSTED reel", p.get("species"), p["reel_link"])
elif cmd == "skip":
    p = find(st, sys.argv[2]); p["carousel" if sys.argv[3] == "carousel" else "reel_status"] = "skipped"; save(st); print("skipped")
elif cmd == "redo":
    p = find(st, sys.argv[2]); p["redo"] = sys.argv[3]; save(st); print("on the redo list")
