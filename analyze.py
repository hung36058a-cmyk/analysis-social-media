"""Tính số liệu cho /phan-tich-mxh. MỌI con số trong báo cáo phải lấy từ output của file này.

Dùng:
    python analyze.py <file_du_lieu.json> <thu_muc_ra>

Ra 2 file trong <thu_muc_ra>: so-lieu.json (đầy đủ) và so-lieu.md (bảng để đọc nhanh).

Nhận 2 dạng đầu vào:
1. File YouTube của ytdata\\yt_fetch.py (có khóa "daily", "videos").
2. File MXH chuẩn hóa (TikTok/Instagram/Threads/Facebook), Claude tự ghi theo mẫu:
   {
     "channel": {"id": "...", "ten": "...", "nen_tang": "tiktok"},
     "nguon": "metricool | vidiq | trinh_duyet | csv",
     "lay_luc": "2026-11-20T10:00:00+08:00",
     "profile": {"followers": 123, "following": 1, "total_likes": 456, "posts": 30},
     "posts": [{"published": "2026-11-10T12:00:00+08:00", "title": "...", "url": "...",
                "duration": 45, "views": 1000, "likes": 50, "comments": 3,
                "shares": 2, "saves": 1, "reposts": null, "nhom": "tùy chọn: nhãn để so nhóm"}]
   }
   - Trường không có thì để null, KHÔNG điền 0.
   - "published" PHẢI có múi giờ (+08:00). Chỉ biết ngày (vd Threads "3 ngày") thì ghi "2026-11-17"
     (không giờ): bài đó không vào bảng giờ đăng.
   - Cũng nhận "YYYYMMDDHHMMSS" (Metricool, giờ Đài Loan) và số epoch giây/mili-giây.
"""
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

TW = timezone(timedelta(hours=8))
SHORT_MAX = 180   # giây: ≤ 180 là Short
YOUNG_DAYS = 3    # < 3 ngày: chưa có số liệu đáng tin
RANK_DAYS = 7     # chỉ xếp hạng/tính trung vị bài ≥ 7 ngày tuổi (views đã gần ổn định)
THIN = 8          # nhóm < 8 bài đủ tuổi = dữ liệu mỏng
THU = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def num(x):
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round((a - b) / b * 100, 1)


def ratio(a, b, k=100):
    if a is None or b in (None, 0):
        return None
    return round(a / b * k, 2)


def parse_time(s, naive_tz=None):
    """Trả (datetime theo giờ TW hoặc None, có_giờ: bool, lỗi: str|None)."""
    if s is None or s == "":
        return None, False, None
    s = str(s).strip()
    try:
        if s.isdigit():
            if len(s) == 14:  # YYYYMMDDHHMMSS (Metricool, giờ TW)
                return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=TW), True, None
            n = int(s)
            if len(s) >= 13:
                n //= 1000
            return datetime.fromtimestamp(n, tz=timezone.utc).astimezone(TW), True, None
        if len(s) == 10:  # chỉ có ngày
            return datetime.fromisoformat(s).replace(tzinfo=TW), False, None
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, OSError, OverflowError):
        return None, False, f"không đọc được thời gian: {s}"
    if t.tzinfo is None:
        if naive_tz is None:
            return None, False, f"thiếu múi giờ: {s}"
        t = t.replace(tzinfo=naive_tz)
    return t.astimezone(TW), True, None


def rows_to_dicts(block):
    cols = (block or {}).get("cols", [])
    return [dict(zip(cols, r)) for r in (block or {}).get("rows", [])]


def sum_col(rows, col):
    vals = [num(r.get(col)) for r in rows]
    vals = [v for v in vals if v is not None]
    return round(sum(vals), 2) if vals else None


def enrich(x, now):
    v = x.get("views")
    eng = [x.get(k) for k in ("likes", "comments", "shares", "saves", "reposts")]
    eng = [e for e in eng if e is not None]
    x["tuong_tac_pct"] = ratio(sum(eng), v) if eng else None
    x["share_pct"] = ratio(x.get("shares"), v)
    p = x.get("published")
    x["published_TW"] = (p.strftime("%Y-%m-%d %H:%M") if x.get("co_gio") else p.strftime("%Y-%m-%d")) if p else None
    x["tuoi_ngay"] = round((now - p).total_seconds() / 86400, 1) if p else None
    x["views_moi_ngay"] = ratio(v, x["tuoi_ngay"], 1) if x["tuoi_ngay"] and x["tuoi_ngay"] > 0 else None
    return x


def short(x, key):
    keep = ["published_TW", "tuoi_ngay", "title", "url", "duration", "views", "views_moi_ngay",
            "so_voi_trung_vi", "avg_view_pct", "avg_duration", "tuong_tac_pct", "share_pct",
            "likes", "comments", "shares", "saves", "reposts", "gained", "nhom"]
    return {k: x.get(k) for k in keep if x.get(k) is not None}


def item_stats(items, now, key="views"):
    out = {}
    groups = defaultdict(list)
    for it in items:
        groups[it["loai"]].append(it)
    for kind, xs in groups.items():
        ranked_pool = [x for x in xs if x[key] is not None and (x["tuoi_ngay"] or 0) >= RANK_DAYS]
        young = [x for x in xs if x["tuoi_ngay"] is None or x["tuoi_ngay"] < YOUNG_DAYS or x[key] is None]
        m = med([x[key] for x in ranked_pool])
        for x in xs:
            x["so_voi_trung_vi"] = ratio(x[key], m, 1) if m and (x["tuoi_ngay"] or 0) >= RANK_DAYS else None
        ranked = sorted(ranked_pool, key=lambda x: x[key], reverse=True)
        n = len(ranked)
        by_hour, by_wd, by_week, by_nhom = (defaultdict(list) for _ in range(4))
        for x in ranked_pool:
            p = x["published"]
            if p and x.get("co_gio"):
                by_hour[f"{p.hour:02d}h"].append(x[key])
            if p:
                by_wd[THU[p.weekday()]].append(x[key])
        for x in xs:  # theo tuần: mọi bài có số liệu (≥3 ngày), để thấy xu hướng theo thời gian
            if x["published"] and x[key] is not None and (x["tuoi_ngay"] or 0) >= YOUNG_DAYS:
                y, w, _ = x["published"].isocalendar()
                by_week[f"{y}-W{w:02d}"].append(x)
            if x.get("nhom") is not None and x in ranked_pool:
                by_nhom[str(x["nhom"])].append(x[key])

        def bang(d):
            return {k: {"so_bai": len(v), "trung_vi": med(v)} for k, v in sorted(d.items())}

        out[kind] = {
            "xep_hang_theo": key,
            "so_bai": len(xs),
            "so_bai_du_7_ngay_de_xep_hang": n,
            "canh_bao_nhom": (f"Mỏng: chỉ {n} bài ≥{RANK_DAYS} ngày tuổi, kết luận chỉ là gợi ý"
                              if n < THIN else None),
            "bai_chua_du_so_lieu_duoi_3_ngay": [short(x, key) for x in young],
            "trung_vi_bai_du_7_ngay": {
                key: m,
                "tuong_tac_pct": med([x["tuong_tac_pct"] for x in ranked_pool]),
                "share_pct": med([x["share_pct"] for x in ranked_pool]),
                "avg_view_pct": med([x.get("avg_view_pct") for x in ranked_pool]),
                "avg_duration": med([x.get("avg_duration") for x in ranked_pool]),
                "duration": med([x.get("duration") for x in ranked_pool]),
                "gained": med([x.get("gained") for x in ranked_pool]),
            },
            "top": [short(x, key) for x in ranked[:5]],
            "duoi": [short(x, key) for x in ranked[max(5, n - 5):]][::-1],
            "theo_gio_dang_TW": bang(by_hour),
            "theo_thu": bang(by_wd),
            "theo_tuan_dang": {k: {"so_bai": len(v), "trung_vi_" + key: med([x[key] for x in v]),
                                   "tuoi_trung_vi_ngay": med([x["tuoi_ngay"] for x in v])}
                               for k, v in sorted(by_week.items())},
            "theo_nhom": bang(by_nhom),
        }
    return out


def nhip_dang(items, ngay_tu, ngay_den):
    days = defaultdict(int)
    for x in items:
        p = x["published"]
        if p and ngay_tu <= p.date() <= ngay_den:
            days[p.date()] += 1
    span = (ngay_den - ngay_tu).days + 1
    total = sum(days.values())
    return {"so_bai_trong_ky": total, "bai_moi_ngay": round(total / span, 2) if span > 0 else None,
            "so_ngay_dang_tu_2_bai": sum(1 for v in days.values() if v >= 2),
            "so_ngay_khong_dang": span - len(days)}


def analyze_youtube(d):
    warns = []
    cur, prev = rows_to_dicts(d["daily"]), rows_to_dicts(d.get("daily_prev"))
    cur_dates = sorted(r["date"] for r in cur if r.get("date"))
    # dữ liệu ngày của API trễ 1–3 ngày: tuổi video tính đến ngày cuối CÓ số liệu
    last = date.fromisoformat(cur_dates[-1]) if cur_dates else date.fromisoformat(d["period"]["to"])
    now = datetime(last.year, last.month, last.day, tzinfo=TW) + timedelta(days=1)

    def zero_days(rows):
        return sum(1 for r in rows if not num(r.get("views")))

    tong = {}
    nc, npv = len(cur), len(prev)
    for col in ["views", "watch_minutes", "gained", "lost", "likes", "comments", "shares"]:
        a, b = sum_col(cur, col), sum_col(prev, col)
        ta = round(a / nc, 2) if a is not None and nc else None
        tb = round(b / npv, 2) if b is not None and npv else None
        tong[col] = {"ky_nay": a, "ky_truoc": b, "tb_ngay_ky_nay": ta, "tb_ngay_ky_truoc": tb,
                     "thay_doi_tb_ngay_pct": pct(ta, tb)}
    g, l = tong["gained"]["ky_nay"], tong["lost"]["ky_nay"]
    gp, lp = tong["gained"]["ky_truoc"], tong["lost"]["ky_truoc"]
    tong["sub_rong"] = {"ky_nay": (g or 0) - (l or 0) if g is not None or l is not None else None,
                        "ky_truoc": (gp or 0) - (lp or 0) if gp is not None or lp is not None else None}
    so_ngay = {"ky_nay_co_so_lieu": nc, "ky_truoc_co_so_lieu": npv,
               "ky_nay_ngay_0_view": zero_days(cur), "ky_truoc_ngay_0_view": zero_days(prev),
               "ngay_cuoi_co_so_lieu": str(last)}
    if nc != npv:
        warns.append(f"Hai kỳ dài khác nhau ({nc} và {npv} ngày có số liệu): chỉ so trung bình/ngày")
    if npv and zero_days(prev) > npv * 0.25:
        warns.append(f"Kỳ trước có {zero_days(prev)}/{npv} ngày 0 view (kênh còn mới): % thay đổi dễ gây hiểu sai")

    items = []
    for r in rows_to_dicts(d["videos"]):
        dur = num(r.get("duration"))
        p, co_gio, _ = parse_time(r.get("published"), naive_tz=timezone.utc)  # YouTube API = UTC
        x = {"title": r.get("title"), "url": r.get("url"), "duration": dur, "published": p, "co_gio": co_gio,
             "views": num(r.get("views")), "likes": num(r.get("likes")), "comments": num(r.get("comments")),
             "shares": num(r.get("shares")), "gained": num(r.get("gained")),
             "avg_view_pct": num(r.get("avg_view_pct")), "avg_duration": num(r.get("avg_duration")),
             "watch_minutes": num(r.get("watch_minutes")),
             "loai": "short" if dur is not None and dur <= SHORT_MAX else "long"}
        items.append(enrich(x, now))

    views_ky = tong["views"]["ky_nay"]

    def phan_bo(key):
        rows = (d.get(key) or {}).get("rows", [])
        return [{"muc": " / ".join(str(c) for c in r[:-1]), "views": num(r[-1]),
                 "ty_le_tren_tong_views_pct": ratio(num(r[-1]), views_ky)} for r in rows]

    quoc_gia = phan_bo("country")
    tw = next((q["ty_le_tren_tong_views_pct"] for q in quoc_gia if q["muc"] == "TW"), 0.0)
    gained_ky = tong["gained"]["ky_nay"]
    chi_so = {
        "sub_moi_tren_1000_views": ratio(gained_ky, views_ky, 1000),
        "comments_ky_nay": tong["comments"]["ky_nay"],
        "ty_le_views_tu_Dai_Loan_pct": tw,
        "nhip_dang_trong_ky": nhip_dang(items, date.fromisoformat(d["period"]["from"]), last),
    }
    if tong["comments"]["ky_nay"] == 0:
        warns.append("Cả kỳ 0 bình luận")
    n_ok = sum(1 for x in items if x["views"] is not None and (x["tuoi_ngay"] or 0) >= RANK_DAYS)
    if n_ok < THIN:
        warns.append(f"Dữ liệu mỏng: chỉ {n_ok} video ≥{RANK_DAYS} ngày tuổi")
    return {
        "nen_tang": "youtube", "kenh": d["channel"], "ky": d.get("period"), "so_ngay": so_ngay,
        "kenh_tong": d.get("channel_stats"), "tong_ky": tong, "chi_so_kenh": chi_so,
        "video_90_ngay": item_stats(items, now),
        "traffic": phan_bo("traffic"), "quoc_gia_top": quoc_gia,
        "tuoi_gioi_tinh_pct": [{"muc": " / ".join(str(c) for c in r[:-1]), "pct": num(r[-1])}
                               for r in (d.get("age_gender") or {}).get("rows", [])],
        "chua_co_trong_API": "Tỷ lệ 'Đã xem / Vuốt qua' của Shorts, người xem quay lại: lấy tay trong YouTube Studio",
        "data_warning": "; ".join(warns) or None,
    }


def analyze_social(d):
    warns = []
    now, _, _ = parse_time(d.get("lay_luc"))
    now = now or datetime.now(TW)
    items, loi_gio = [], []
    for p in d.get("posts", []):
        t, co_gio, err = parse_time(p.get("published"))
        if err:
            loi_gio.append(err)
        x = {k: num(p.get(k)) for k in ("views", "likes", "comments", "shares", "saves", "reposts", "duration")}
        x.update({"title": (p.get("title") or "")[:120], "url": p.get("url"), "published": t, "co_gio": co_gio,
                  "nhom": p.get("nhom"), "loai": "bai"})
        items.append(enrich(x, now))
    if loi_gio:
        warns.append(f"{len(loi_gio)} bài lỗi thời gian (vd: {loi_gio[0]})")
    no_views = all(x["views"] is None for x in items)
    key = "likes" if no_views else "views"
    if no_views:
        warns.append("Không có lượt xem: xếp hạng theo like")
    if d.get("nguon") in ("vidiq", "trinh_duyet"):
        warns.append("Ảnh chụp công khai một thời điểm, không có kỳ trước để so")
    dated = [x["published"] for x in items if x["published"]]
    tong_cmt = sum(x["comments"] or 0 for x in items)
    tong_v = sum(x["views"] or 0 for x in items) if not no_views else None
    n_ok = sum(1 for x in items if x[key] is not None and (x["tuoi_ngay"] or 0) >= RANK_DAYS)
    if n_ok < THIN:
        warns.append(f"Dữ liệu mỏng: chỉ {n_ok} bài ≥{RANK_DAYS} ngày tuổi")
    return {
        "nen_tang": d["channel"].get("nen_tang"), "kenh": d["channel"], "nguon": d.get("nguon"),
        "lay_luc": d.get("lay_luc"), "profile": d.get("profile", {}),
        "so_bai_lay_duoc": len(items),
        "chi_so_kenh": {
            "tong_views_cac_bai": tong_v,
            "tong_comments_cac_bai": tong_cmt,
            "comments_tren_1000_views": ratio(tong_cmt, tong_v, 1000) if tong_v else None,
            "nhip_dang_30_ngay_cuoi": nhip_dang(items, (now - timedelta(days=30)).date(), now.date()) if dated else None,
        },
        "bai": item_stats(items, now, key=key),
        "ghi_chu_nguon": d.get("ghi_chu"),
        "data_warning": "; ".join(warns) or None,
    }


def to_md(r):
    L = [f"# Số liệu: {r['kenh'].get('ten')} ({r['nen_tang']})", ""]
    if r.get("data_warning"):
        L += [f"> CẢNH BÁO: {r['data_warning']}", ""]
    if r["nen_tang"] == "youtube":
        L += [f"Kỳ: {r['ky']['from']} → {r['ky']['to']} · {r['so_ngay']}", "",
              "| Chỉ số | Kỳ này | Kỳ trước | TB/ngày nay | TB/ngày trước | Đổi TB/ngày % |", "|---|---|---|---|---|---|"]
        for k, v in r["tong_ky"].items():
            L.append(f"| {k} | {v.get('ky_nay')} | {v.get('ky_truoc')} | {v.get('tb_ngay_ky_nay', '')} | "
                     f"{v.get('tb_ngay_ky_truoc', '')} | {v.get('thay_doi_tb_ngay_pct', '')} |")
        L += ["", f"Tổng kênh: {r['kenh_tong']}", f"Chỉ số kênh: {r['chi_so_kenh']}", ""]
        L += ["## Traffic (% trên tổng views kỳ)"] + [f"- {t['muc']}: {t['views']} ({t['ty_le_tren_tong_views_pct']}%)" for t in r["traffic"]]
        L += ["", "## Quốc gia (% trên tổng views kỳ)"] + [f"- {t['muc']}: {t['views']} ({t['ty_le_tren_tong_views_pct']}%)" for t in r["quoc_gia_top"]]
        L += ["", f"## Tuổi/giới (%): {[(t['muc'], t['pct']) for t in r['tuoi_gioi_tinh_pct']]}"]
        groups = r["video_90_ngay"]
    else:
        L += [f"Nguồn: {r.get('nguon')} lúc {r.get('lay_luc')} · {r['so_bai_lay_duoc']} bài",
              f"Hồ sơ: {r['profile']}", f"Chỉ số kênh: {r['chi_so_kenh']}"]
        groups = r["bai"]
    for kind, g in groups.items():
        k = g["xep_hang_theo"]
        L += ["", f"## {kind.upper()}: {g['so_bai']} bài, {g['so_bai_du_7_ngay_de_xep_hang']} bài ≥7 ngày để xếp hạng"]
        if g["canh_bao_nhom"]:
            L.append(f"> {g['canh_bao_nhom']}")
        L += [f"Trung vị (bài ≥7 ngày): {g['trung_vi_bai_du_7_ngay']}", "", "### Top"]
        fmt = lambda x: (f"- {x.get(k)} {k} (x{x.get('so_voi_trung_vi')} trung vị, {x.get('views_moi_ngay')}/ngày, "
                         f"xem {x.get('avg_view_pct')}%) | {x.get('published_TW')} | {x.get('title')}")
        L += [fmt(x) for x in g["top"]]
        if g["duoi"]:
            L += ["", "### Dưới"] + [fmt(x) for x in g["duoi"]]
        L += ["", f"Theo giờ đăng (TW): {g['theo_gio_dang_TW']}", f"Theo thứ: {g['theo_thu']}",
              f"Theo tuần đăng: {g['theo_tuan_dang']}"]
        if g["theo_nhom"]:
            L.append(f"Theo nhóm: {g['theo_nhom']}")
        L.append(f"Chưa đủ số liệu (<3 ngày): {len(g['bai_chua_du_so_lieu_duoi_3_ngay'])} bài")
    return "\n".join(L) + "\n"


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, out_dir = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        d = json.load(f)
    r = analyze_youtube(d) if "daily" in d and "videos" in d else analyze_social(d)
    r["file_nguon"] = os.path.abspath(src)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "so-lieu.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1, default=str)
    with open(os.path.join(out_dir, "so-lieu.md"), "w", encoding="utf-8") as f:
        f.write(to_md(r))
    print("OK", os.path.join(out_dir, "so-lieu.json"))


if __name__ == "__main__":
    main()
