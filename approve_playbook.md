# Approval playbook — tomorrow's Instagram posts (@nayeem.wildlife)

Ishrath approves on a phone-friendly page with buttons. He must not have to type or read much.
APPROVAL PAGE: https://claude.ai/artifact/CVGWgiSBjt5MAVqrJeUrLE  (artifact with a `posts` database + asset store)
Nothing is published from this session (two other scheduled tasks post at 7:58 am and 8:28 pm what is
marked approved in R2 state). This session turns his taps into approvals.

Load these tools with ToolSearch: Artifact, ArtifactData, PushNotification, mcp__claude-code-remote__send_later.
CODE = the folder where the nayeem-posting repo was cloned. Every daily.py command:
`cd CODE && PE_ENV=~/pe/.env python3 daily.py ...` (run it in CODE so today/ and logo.png are found).

## A. Evening run (the scheduled start)
1. TOMORROW = tomorrow in America/Vancouver (YYYY-MM-DD).
2. `daily.py status`, `daily.py next` → today/today.json, slides, today/reel.mp4.
3. Captions (website style). Rewrite any that don't fit:
   line 1 a 1–4 word title like "Perched" / "Pride at the water" (no emoji, no full stop) · blank line ·
   one sentence ≤ ~15 words, ≤ 1 emoji · blank line · EXACTLY 5 hashtags, last #nayeemwildlife.
   Count animals correctly (a reflection is not a second animal).
4. Music: `daily.py music "<query>"` (2–3 queries that fit species + mood). Pick 3 tracks; look up BPM by web
   search where possible. If the first track's BPM is known: `daily.py recut <reel slug> <bpm>`.
5. Put the posts on the approval page:
   a. `Artifact` action "read" on the APPROVAL PAGE url (required before uploading).
   b. Clean up: `ArtifactData` list collection "posts"; delete docs whose date < TOMORROW (pass if_version),
      and delete their assets (`Artifact` action "delete", url + path = asset id, the part after /_blob/).
   c. Copy today/*.jpg slides and today/reel.mp4 into a folder under your scratchpad/working dir, make a poster
      `ffmpeg -y -ss 1 -i reel.mp4 -frames:v 1 -q:v 3 poster.jpg`, then upload them with ONE `Artifact` publish:
      url = APPROVAL PAGE, asset: true, file_paths: [...]. Use the returned "/_blob/<id>" urls verbatim.
   d. `ArtifactData` batch set two docs in "posts":
      `<TOMORROW>-carousel`: {date, time:"8:00 am", kind:"carousel", slug, species, caption, slides:[urls in order], status:"pending"}
      `<TOMORROW>-reel`: {date, time:"8:30 pm", kind:"reel", slug, species, caption, video:url, poster:url,
                          tracks:[{id:audio_id, label:"Title – Artist", note:"120 BPM" or mood, bpm:number|null}], status:"pending"}
      (theme day tomorrow? add `<TOMORROW>-theme`: kind "carousel", time "8:00 am", species = theme, caption, slides
       = first slide of up to 10 posts of that species, slug "theme:<species>", status "pending")
6. PushNotification: "Tomorrow: <Species> carousel 8 am + <Species> Reel 8:30 pm — tap to approve" and include the
   APPROVAL PAGE link. Then one short SendUserMessage line with the same link. No long text.
7. Low buffer (< 10 carousels or < 10 Reels waiting): add "· only N left, batch evening due" to that line.
8. send_later (this session) at: 10:30 pm tonight ("reminder check"), 7:40 am TOMORROW ("carousel sync"),
   8:10 pm TOMORROW ("reel sync"). Convert Pacific to UTC.

## B. "reminder check" (10:30 pm)
Read both docs. If any is still "pending", one gentle PushNotification with the page link. Otherwise nothing.

## C. "carousel sync" (7:40 am) — and theme doc if present
Read `<DATE>-carousel` (DATE = today Pacific). Caption = edited_caption if set, else caption → write to a file.
- status "ok": `daily.py approve carousel <slug> <DATE> <caption_file>`  (theme: `daily.py theme "<species>" <caption_file>` publishes directly)
- "skip": `daily.py skip <slug> carousel` · "reject": `daily.py redo <slug> "rejected on approval page"`
- "pending": do nothing (unapproved posts are never published).
Then update the doc: add `synced: true`.

## D. "reel sync" (8:10 pm)
Read `<DATE>-reel`. If "ok": chosen = track_id (default first track). If the chosen track has a bpm and it
differs from the one already cut, `daily.py recut <slug> <bpm>` first. Caption file as above, then
`daily.py approve reel <slug> <DATE> <track_id> "<label>" <caption_file>`.  skip / reject as in C.
Update the doc with `synced: true`.

## Rules
Never post stories or to Facebook. Never change or delete published posts. Never print or repeat key values.
If something fails, one plain-sentence PushNotification.
