# nayeem-posting
Cloud side of Ishrath's daily Instagram posting (@nayeem.wildlife). Used by the scheduled tasks:
approval page + publish at 8:00 am / 8:30 pm. No keys in this repo — they come from the task's KEYS section.
- daily.py — status / next / music / recut / approve / due / theme / skip / redo
- pe_cloud.py — R2 storage + Instagram Graph API helpers
- reel.py — builds the 9:16 photo Reel (cuts on the song's bar lines when a BPM is given)
- upload_batch.py — after a batch evening: build Reels and upload posts to R2
- approve_playbook.md — what the evening approval task does
