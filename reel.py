#!/usr/bin/env python3
"""Photo Reel from one finished post folder (runs in the cloud; needs Pillow, numpy, ffmpeg).
   reel.py <post_dir> <out.mp4> <logo.png> [bpm]
With a bpm, every cut lands on a bar line of the track (4 beats a bar): long shots 2 bars, close shots 1 bar.
Uses contest/*-pe-contest.jpg (full frame, denoised, no logo) and *-pe-contest-bw.jpg (his Monochrome).
Shots: wide 9:16 push-in -> 16:10 panorama glide -> medium -> close-up on the eyes -> B&W wide -> logo.
The video carries a silent audio track; the music is attached by Instagram (Audio API) when publishing."""
import glob, json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
Image.MAX_IMAGE_PIXELS = None
W, H, FPS = 1080, 1920, 30
SHOT = 2.6     # seconds per shot
XF = 0.45      # crossfade

post, out, logo_p = sys.argv[1:4]
BPM = float(sys.argv[4]) if len(sys.argv) > 4 else 0
c = glob.glob(os.path.join(post, "contest", "*-pe-contest.jpg"))
if not c: sys.exit("no contest export in " + post)
src = Image.open(c[0]).convert("RGB")
cb = glob.glob(os.path.join(post, "contest", "*-pe-contest-bw.jpg"))
src_bw = Image.open(cb[0]).convert("RGB") if cb else ImageOps.grayscale(src).convert("RGB")
if src_bw.size != src.size: src_bw = src_bw.resize(src.size, Image.LANCZOS)
plan = json.load(open(os.path.join(post, "plan.json")))
pw, ph = plan["preview_size"]; k = src.width / pw
box = {cr["name"]: [v * k for v in cr["upright_box"]] for cr in plan["crops"]}
v = plan.get("vision", {})
hb = v.get("head") or v.get("body") or [0.4, 0.4, 0.6, 0.6]
head = [hb[0] * src.width, hb[1] * src.height, hb[2] * src.width, hb[3] * src.height]
eyes = v.get("eyes") or []
ex = np.mean([(e[0] + e[2]) / 2 for e in eyes]) * src.width if eyes else (head[0] + head[2]) / 2
ey = np.mean([(e[1] + e[3]) / 2 for e in eyes]) * src.height if eyes else (head[1] + head[3]) / 2
hh = max(head[3] - head[1], 1)

def nine16(cx, cy, ch):
    ch = min(ch, src.height, src.width * 16 / 9); cw = ch * 9 / 16
    l = min(max(cx - cw / 2, 0), src.width - cw); t = min(max(cy - ch / 2, 0), src.height - ch)
    return (l, t, l + cw, t + ch)

def render(im, b, os_=1.15):
    return im.resize((int(W * os_), int(H * os_)), Image.LANCZOS, box=tuple(b))

wide_box = box.get("story-9x16") or nine16((head[0] + head[2]) / 2, (head[1] + head[3]) / 2, src.height)
wide = render(src, wide_box)
wide_bw = render(src_bw, wide_box)
mid_h = max(hh * 4.0, src.height * 0.45)
mid = render(src, nine16((head[0] + head[2]) / 2, ey + 0.1 * mid_h, mid_h))
face_h = max(hh * 2.2, src.height * 0.22)
face = render(src, nine16(ex, ey + 0.05 * face_h, face_h))
tvb = box.get("tv-16x10")
tv = src.resize((round((tvb[2] - tvb[0]) * H / (tvb[3] - tvb[1])), H), Image.LANCZOS, box=tuple(tvb)) if tvb else None
logo = Image.open(logo_p).convert("RGBA")

def zoom(base, z):
    bw_, bh = base.size; cw, ch = bw_ / z, bh / z
    l, t = (bw_ - cw) / 2, (bh - ch) / 2
    return base.resize((W, H), Image.LANCZOS, box=(l, t, l + cw, t + ch))

end_bg = ImageEnhance.Brightness(zoom(wide_bw, 1.0).filter(ImageFilter.GaussianBlur(18))).enhance(0.35)

def logo_frame(u):
    fr = end_bg.copy()
    a = max(0.0, min(1.0, (u - 0.12) / 0.45)); a = a * a * (3 - 2 * a)
    lw = int(W * 0.56 * (0.90 + 0.10 * a))
    lg = logo.resize((lw, round(lw * logo.height / logo.width)), Image.LANCZOS)
    glow = lg.filter(ImageFilter.GaussianBlur(22))
    for layer, op in ((glow, 0.35), (lg, 1.0)):
        al = layer.getchannel("A").point(lambda p: int(p * a * op))
        layer = layer.copy(); layer.putalpha(al)
        fr.paste(layer, ((W - lw) // 2, (H - lg.height) // 2 - 60), layer)
    return fr

if BPM:
    bar = 240.0 / BPM
    while bar < 1.6: bar *= 2          # very fast songs: cut every 2 bars
    while bar > 4.2: bar /= 2
    L, S = (2 if bar < 2.6 else 1), 1  # bars per long / short shot
    segs = [("zoom", wide, 1.00, 1.07, L * bar)]
    if tv is not None and tv.width > W * 1.3: segs.append(("pan", tv, 0, 1, L * bar * 1.5 if L * bar < 3 else L * bar))
    segs += [("zoom", mid, 1.00, 1.06, S * bar), ("zoom", face, 1.00, 1.05, S * bar),
             ("zoom", wide_bw, 1.07, 1.00, L * bar), ("logo", None, 0, 1, max(3.0, 2 * bar))]
    # crossfades centred on the bar lines: each shot runs XF/2 past its cut on both sides
    segs = [(k, im, a, b, d + XF) for (k, im, a, b, d) in segs]
else:
    segs = [("zoom", wide, 1.00, 1.07, SHOT)]
    if tv is not None and tv.width > W * 1.3: segs.append(("pan", tv, 0, 1, SHOT * 1.5))
    segs += [("zoom", mid, 1.00, 1.06, SHOT), ("zoom", face, 1.00, 1.05, SHOT),
             ("zoom", wide_bw, 1.07, 1.00, SHOT), ("logo", None, 0, 1, 3.2)]

def frame(seg, u):
    kind, img, a, b, d = seg
    e = u * u * (3 - 2 * u)
    if kind == "zoom": return zoom(img, a + (b - a) * e)
    if kind == "pan":
        x = (img.width - W) * e
        return img.crop((round(x), 0, round(x) + W, H))
    return logo_frame(u)

starts, acc = [], 0
for s in segs:
    starts.append(acc); acc += s[4] - XF
total = acc + XF
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                       "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.2f}",
                       "-movflags", "+faststart", out], stdin=subprocess.PIPE)
for n in range(int(total * FPS)):
    t = n / FPS
    act = [i for i, s in enumerate(segs) if starts[i] <= t < starts[i] + s[4]]
    i = act[-1]
    fr = frame(segs[i], (t - starts[i]) / segs[i][4])
    if len(act) > 1:
        j = act[0]
        fr = Image.blend(frame(segs[j], (t - starts[j]) / segs[j][4]), fr, max(0, min(1, (t - starts[i]) / XF)))
    ff.stdin.write(fr.tobytes())
ff.stdin.close(); ff.wait()
print(f"reel: {out} ({total:.1f}s)")
