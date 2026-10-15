"""Shared helpers for the cloud side: settings, R2 storage, Instagram publishing. Never prints secrets.
Settings come from environment variables, or from a .env file given in PE_ENV."""
import json, os, time, urllib.error, urllib.parse, urllib.request

def settings():
    s = dict(os.environ)
    p = os.environ.get("PE_ENV")
    if p and os.path.exists(p):
        for l in open(p):
            if "=" in l and not l.startswith("#"):
                k, v = l.strip().split("=", 1); s.setdefault(k, v)
    return s

S = settings()

# ---------- R2 ----------
def r2():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=f"https://{S['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=S["R2_ACCESS_KEY_ID"], aws_secret_access_key=S["R2_SECRET_ACCESS_KEY"],
                        region_name="auto", config=Config(signature_version="s3v4"))
BUCKET = S.get("R2_BUCKET", "nayeem-posts")

def put_file(path, key, ctype):
    r2().upload_file(path, BUCKET, key, ExtraArgs={"ContentType": ctype})

def put_json(key, obj):
    r2().put_object(Bucket=BUCKET, Key=key, Body=json.dumps(obj, indent=1).encode(), ContentType="application/json")

def get_json(key, default=None):
    try: return json.loads(r2().get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except Exception: return default

def get_file(key, path):
    r2().download_file(BUCKET, key, path)

def link(key, hours=6):
    return r2().generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=hours * 3600)

# ---------- Instagram (Graph API, Facebook Login) ----------
G = "https://graph.facebook.com/"

def graph(method, path, **params):
    params["access_token"] = S["META_PAGE_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(G + path + "?" + data.decode())
    else:
        req = urllib.request.Request(G + path, data=data, method="POST")
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        err = json.loads(e.read() or b"{}").get("error", {})
        raise RuntimeError(f"Instagram error on {path}: {err.get('message')} (code {err.get('code')})")

def wait_ready(cid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = graph("GET", cid, fields="status_code,status").get("status_code")
        if st == "FINISHED": return
        if st in ("ERROR", "EXPIRED"): raise RuntimeError(f"container {cid}: {st}")
        time.sleep(8)
    raise RuntimeError(f"container {cid}: not ready after {timeout}s")

def publish_carousel(image_urls, caption):
    ig = S["IG_USER_ID"]
    kids = []
    for u in image_urls[:10]:
        kids.append(graph("POST", f"{ig}/media", image_url=u, is_carousel_item="true")["id"])
    for k in kids: wait_ready(k)
    c = graph("POST", f"{ig}/media", media_type="CAROUSEL", children=",".join(kids), caption=caption)["id"]
    wait_ready(c)
    return graph("POST", f"{ig}/media_publish", creation_id=c)["id"]

def publish_reel(video_url, caption, audio_id=None, cover_url=None):
    ig = S["IG_USER_ID"]
    p = dict(media_type="REELS", video_url=video_url, caption=caption, share_to_feed="true")
    if audio_id:
        p["audio_configuration"] = json.dumps({"audio_id": str(audio_id), "audio_volume": 100, "video_volume": 0})
    if cover_url: p["cover_url"] = cover_url
    c = graph("POST", f"{ig}/media", **p)["id"]
    wait_ready(c, 900)
    return graph("POST", f"{ig}/media_publish", creation_id=c)["id"]

def publish_story(url, video=False):
    """Instagram story (image or video). The API can't add stickers or a link to the post."""
    ig = S["IG_USER_ID"]
    p = dict(media_type="STORIES")
    p["video_url" if video else "image_url"] = url
    c = graph("POST", f"{ig}/media", **p)["id"]
    wait_ready(c, 900 if video else 300)
    return graph("POST", f"{ig}/media_publish", creation_id=c)["id"]

# ---------- Facebook Page (needs pages_manage_posts) ----------
def fb_photos(image_urls, message):
    page = S["META_PAGE_ID"]
    ids = [graph("POST", f"{page}/photos", url=u, published="false")["id"] for u in image_urls[:10]]
    att = {f"attached_media[{i}]": json.dumps({"media_fbid": x}) for i, x in enumerate(ids)}
    return graph("POST", f"{page}/feed", message=message, **att)["id"]

def fb_reel(video_url, description):
    page = S["META_PAGE_ID"]
    vid = graph("POST", f"{page}/video_reels", upload_phase="start")["video_id"]
    req = urllib.request.Request(f"https://rupload.facebook.com/video-upload/v21.0/{vid}", method="POST",
                                 headers={"Authorization": "OAuth " + S["META_PAGE_TOKEN"], "file_url": video_url})
    json.load(urllib.request.urlopen(req, timeout=300))
    return graph("POST", f"{page}/video_reels", upload_phase="finish", video_id=vid,
                 video_state="PUBLISHED", description=description).get("success")

def permalink(media_id):
    return graph("GET", media_id, fields="permalink").get("permalink")

def find_music(query):
    """Licensed tracks from Instagram's music library (needs the user token)."""
    q = dict(audio_type="music", user_id=S["IG_USER_ID"], access_token=S["META_USER_TOKEN"])
    if query: q["search_query"] = query
    r = json.load(urllib.request.urlopen(G + "ig_audio?" + urllib.parse.urlencode(q), timeout=60))
    return r.get("audio", [])
