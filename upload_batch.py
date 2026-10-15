#!/usr/bin/env python3
"""After a batch evening: build each new post's Reel and upload post + Reel to R2.
   upload_batch.py <posts_root_dir> <progress.json> <logo.png>
R2 layout: posts/<slug>/slides/NN-*.jpg, posts/<slug>/reel.mp4, posts/<slug>/caption.txt, posts/<slug>/meta.json
and state/posts.json (the posting list the daily task works from)."""
import glob, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_cloud as pc

root, prog_p, logo = sys.argv[1:4]
prog = json.load(open(prog_p))
state = pc.get_json("state/posts.json", {"posts": []})
known = {p["key"] for p in state["posts"]}
here = os.path.dirname(os.path.abspath(__file__))
for key, rec in prog.get("made", {}).items():
    if rec.get("status") != "made" or key in known and not rec.get("redo"): continue
    post = os.path.join(root, os.path.basename(rec["post"]))
    if not os.path.isdir(post): print("missing folder", post); continue
    slug = re.sub(r"[^A-Za-z0-9]+", "-", os.path.basename(post)).strip("-").lower() + "-" + rec["name"].lower()
    plan = json.load(open(os.path.join(post, "plan.json")))
    slides = sorted(glob.glob(os.path.join(post, "[0-9][0-9]-*.jpg")))
    reel = os.path.join(post, "reel.mp4")
    import shutil
    has_reel = False
    if shutil.which("ffmpeg"):
        subprocess.run([sys.executable, os.path.join(here, "reel.py"), post, reel, logo], check=True)
        has_reel = True
    keys = []
    for s in slides:
        k = f"posts/{slug}/slides/{os.path.basename(s)}"; pc.put_file(s, k, "image/jpeg"); keys.append(k)
    if has_reel: pc.put_file(reel, f"posts/{slug}/reel.mp4", "video/mp4")
    # reel sources (so a Reel can be re-cut in the cloud to another song's tempo), downscaled to 6000 px
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    for f in glob.glob(os.path.join(post, "contest", "*-pe-contest*.jpg")):
        im = Image.open(f).convert("RGB"); im.thumbnail((6000, 6000), Image.LANCZOS)
        tmp = "/tmp/pe-src.jpg"; im.save(tmp, quality=90)
        pc.put_file(tmp, f"posts/{slug}/src/{os.path.basename(f)}", "image/jpeg")
    pc.put_file(os.path.join(post, "plan.json"), f"posts/{slug}/src/plan.json", "application/json")
    st = []
    cap = open(os.path.join(post, "caption.txt")).read().strip()
    parts = rec["path"].split("/Wildlife/")[-1].split("/")
    meta = {"key": key, "slug": slug, "name": rec["name"], "species": plan.get("species"),
            "location": " / ".join(parts[:3]) if len(parts) > 1 else "", "alt_text": plan.get("alt_text", ""),
            "slides": keys, "reel": f"posts/{slug}/reel.mp4",  "caption": cap,
            "schedule": rec.get("schedule", True), "carousel": "pending",
            "reel_status": "pending" if has_reel else "needs_build"}
    pc.put_json(f"posts/{slug}/meta.json", meta)
    state["posts"] = [p for p in state["posts"] if p["key"] != key] + [meta]
    print("uploaded", slug, len(keys), "slides" + (" + reel" if has_reel else " (Reel built later in the cloud)"))
pc.put_json("state/posts.json", state)
print("posting list:", sum(1 for p in state["posts"] if p["schedule"] and p["carousel"] == "pending"), "carousels waiting")
