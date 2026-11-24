"""Kéo số liệu YouTube Analytics cho nhiều kênh (miễn phí, chạy trên máy bạn).

Cài 1 lần:
    pip install google-api-python-client google-auth-oauthlib

Dùng:
    python yt_fetch.py add            # thêm 1 kênh (mở trình duyệt đăng nhập Google, chọn đúng kênh)
    python yt_fetch.py list           # xem các kênh đã thêm
    python yt_fetch.py fetch          # kéo số liệu mọi kênh, 28 ngày
    python yt_fetch.py fetch 7        # kéo số liệu 7 ngày

Cần file client_secret.json (OAuth Desktop app) nằm cùng thư mục.
Kết quả: data/<channel_id>_<YYYY-MM-DD>.json  (đúng định dạng analyze.py của skill /phan-tich-kenh)
"""
import json
import os
import re
import sys
import time
import traceback
from datetime import date, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = os.path.join(HERE, "client_secret.json")
TOKENS = os.path.join(HERE, "tokens")
DATA = os.path.join(HERE, "data")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


# ---------- auth ----------
def load_creds(path):
    creds = Credentials.from_authorized_user_file(path, SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        with open(path, "w") as f:
            f.write(creds.to_json())
    return creds


def add_channel():
    if not os.path.exists(SECRET):
        sys.exit("Thiếu client_secret.json trong thư mục " + HERE)
    flow = InstalledAppFlow.from_client_secrets_file(SECRET, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    yt = build("youtube", "v3", credentials=creds)
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    if not items:
        sys.exit("Tài khoản này chưa có kênh YouTube. Chạy lại và chọn đúng kênh.")
    ch = items[0]
    os.makedirs(TOKENS, exist_ok=True)
    with open(os.path.join(TOKENS, ch["id"] + ".json"), "w") as f:
        f.write(creds.to_json())
    print(f"Đã thêm: {ch['snippet']['title']}  (account_id: {ch['id']})")


def list_channels():
    if not os.path.isdir(TOKENS):
        return []
    return [os.path.join(TOKENS, f) for f in os.listdir(TOKENS) if f.endswith(".json")]


# ---------- helpers ----------
def iso_dur(s):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def report(ya, start, end, metrics, dimensions=None, filters=None, sort=None, max_results=None):
    kw = dict(ids="channel==MINE", startDate=str(start), endDate=str(end), metrics=metrics)
    if dimensions:
        kw["dimensions"] = dimensions
    if filters:
        kw["filters"] = filters
    if sort:
        kw["sort"] = sort
    if max_results:
        kw["maxResults"] = max_results
    for lan in range(4):  # Google đôi khi trả lỗi 500 tạm thời → thử lại
        try:
            r = ya.reports().query(**kw).execute()
            break
        except Exception as e:
            if lan == 3 or " 50" not in str(e)[:40]:
                raise
            time.sleep(5 * (lan + 1))
    return [h["name"] for h in r.get("columnHeaders", [])], r.get("rows", []) or []


def safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:  # kênh nhỏ có thể không có dữ liệu demographics
        print("  (bỏ qua:", str(e)[:120], ")")
        return [], []


DAILY = "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost,likes,comments,shares"
DAILY_COLS = ["views", "watch_minutes", "avg_duration", "gained", "lost", "likes", "comments", "shares"]
VIDEO = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained"


def daily_block(ya, start, end):
    cols, rows = report(ya, start, end, DAILY, dimensions="day", sort="day")
    # API trả cột day trước → đưa date ra cuối cho khớp analyze.py
    return {"cols": DAILY_COLS + ["date"], "rows": [r[1:] + [r[0]] for r in rows]}


def recent_uploads(yt, channel_id, since):
    uploads = "UU" + channel_id[2:]
    ids, token = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                    maxResults=50, pageToken=token).execute()
        stop = False
        for it in r.get("items", []):
            pub = it["contentDetails"].get("videoPublishedAt", "")[:10]
            if pub and pub < str(since):
                stop = True
                break
            ids.append(it["contentDetails"]["videoId"])
        token = r.get("nextPageToken")
        if stop or not token:
            return ids


def video_block(yt, ya, ids, start, end):
    cols = ["published", "title", "url", "duration", "views", "watch_minutes", "avg_duration",
            "avg_view_pct", "likes", "comments", "shares", "gained"]
    rows = []
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        meta = yt.videos().list(part="snippet,contentDetails", id=",".join(batch)).execute()
        info = {v["id"]: v for v in meta.get("items", [])}
        _, stats = safe(report, ya, start, end, VIDEO, dimensions="video", filters="video==" + ",".join(batch))
        stat = {r[0]: r[1:] for r in stats}
        for vid in batch:
            v = info.get(vid)
            if not v:
                continue
            s = stat.get(vid, [None] * 8)
            rows.append([v["snippet"]["publishedAt"][:19], v["snippet"]["title"],
                         "https://www.youtube.com/watch?v=" + vid,
                         iso_dur(v["contentDetails"]["duration"])] + list(s))
    return {"cols": cols, "rows": rows}


def fetch(days=28):
    paths = list_channels()
    if not paths:
        sys.exit("Chưa có kênh nào. Chạy: python yt_fetch.py add")
    os.makedirs(DATA, exist_ok=True)
    end = date.today() - timedelta(days=1)  # số liệu hôm nay chưa đủ
    start = end - timedelta(days=days - 1)
    p_end, p_start = start - timedelta(days=1), start - timedelta(days=days)
    v_start = end - timedelta(days=89)
    loi = []
    for p in paths:
        try:
            fetch_one(p, start, end, p_start, p_end, v_start)
        except Exception:
            loi.append(os.path.basename(p))
            traceback.print_exc()
    if loi:
        sys.exit("LOI kenh: " + ", ".join(loi))


def fetch_one(p, start, end, p_start, p_end, v_start):
    if True:
        creds = load_creds(p)
        yt = build("youtube", "v3", credentials=creds)
        ya = build("youtubeAnalytics", "v2", credentials=creds)
        ch = yt.channels().list(part="snippet,statistics", mine=True).execute()["items"][0]
        print("Đang kéo:", ch["snippet"]["title"])
        out = {
            "channel": {"id": ch["id"], "ten": ch["snippet"]["title"], "nhan_dien_short": "duration"},
            "channel_stats": ch["statistics"],
            "period": {"from": str(start), "to": str(end)},
            "daily": daily_block(ya, start, end),
            "daily_prev": daily_block(ya, p_start, p_end),
            "videos": video_block(yt, ya, recent_uploads(yt, ch["id"], v_start), v_start, end),
        }
        c, r = safe(report, ya, start, end, "views", dimensions="insightTrafficSourceType", sort="-views")
        out["traffic"] = {"cols": c, "rows": r}
        c, r = safe(report, ya, start, end, "views", dimensions="country", sort="-views", max_results=10)
        out["country"] = {"cols": c, "rows": r}
        c, r = safe(report, ya, start, end, "viewerPercentage", dimensions="ageGroup,gender")
        out["age_gender"] = {"cols": c, "rows": r}
        fn = os.path.join(DATA, f"{ch['id']}_{date.today()}.json")
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print("  ->", fn)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "add":
        add_channel()
    elif cmd == "list":
        for p in list_channels():
            print(os.path.basename(p)[:-5])
    elif cmd == "fetch":
        fetch(int(sys.argv[2]) if len(sys.argv) > 2 else 28)
    else:
        print(__doc__)
