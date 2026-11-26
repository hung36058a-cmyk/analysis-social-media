"""Bản tin TUẦN của /phan-tich-mxh: máy tính hết, Claude không phải đọc số liệu thô.

Dùng:  python -X utf8 tom_tat_tuan.py
Ra:    bao-cao\\tuan\\<YYYY-MM-DD>\\thu.txt (thư gửi Gmail) + tom-tat.json (để tuần sau so).
In:    dòng cuối = 1 câu ngắn cho thông báo điện thoại.
Mọi con số trong thư đến từ file YouTube API mới nhất (ytdata\\data) qua analyze.analyze_youtube,
nên KHÔNG cần agent phản biện số liệu.
"""
import glob
import json
import os
import re
import sys
from datetime import date

import yaml

G = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, G)
from analyze import analyze_youtube, num, rows_to_dicts  # noqa: E402

MOC = date(2027, 3, 1)          # mốc bật kiếm tiền người dùng chốt 26/11/2026
SUB_CAN = 500                   # YPP bậc thấp
SHORT_VIEW_CAN_NGAY = 3_000_000 / 90


def kenh_active():
    txt = open(os.path.join(G, "kenh.md"), encoding="utf-8").read()
    for block in re.findall(r"```yaml\n(.*?)```", txt, re.S):
        k = yaml.safe_load(block)
        if k and k.get("trang_thai") == "active":
            yt = next((n for n in k.get("nen_tang") or [] if n.get("mang") == "youtube" and n.get("account_id")), None)
            if yt:
                yield k, yt["account_id"]


def f(x, nd=0):
    if x is None:
        return "?"
    return f"{x:,.{nd}f}".replace(",", "_").replace(".", ",").replace("_", ".")  # kiểu Việt: 1.234,5


def mot_kenh(k, acc, hom_nay):
    files = sorted(glob.glob(os.path.join(G, "ytdata", "data", f"{acc}_*.json")))
    if not files:
        return {"id": k["id"], "ten": k["ten"], "loi": "chưa có file YouTube API"}
    d = json.load(open(files[-1], encoding="utf-8"))
    r = analyze_youtube(d)
    tuoi_file = (hom_nay - date.fromisoformat(os.path.basename(files[-1])[-15:-5])).days
    daily = [x for x in rows_to_dicts(d["daily"]) if x.get("date")]
    daily.sort(key=lambda x: x["date"])
    d7 = daily[-7:]
    s = lambda rows, c: sum(num(x.get(c)) or 0 for x in rows)
    nd = len(daily) or 1
    sub = int(num(r["kenh_tong"].get("subscriberCount")) or 0)
    sub_rong_7 = s(d7, "gained") - s(d7, "lost")
    sub_tuan_tb = (r["tong_ky"]["sub_rong"]["ky_nay"] or 0) / nd * 7
    tuan_con = max((MOC - hom_nay).days / 7, 0.1)
    can_tuan = max(SUB_CAN - sub, 0) / tuan_con
    traffic = {t["muc"]: t for t in r["traffic"]}
    short_pct = (traffic.get("SHORTS") or {}).get("ty_le_tren_tong_views_pct") or 0
    views_ngay = r["tong_ky"]["views"]["tb_ngay_ky_nay"] or 0
    ext = traffic.get("EXT_URL") or {}
    vs = r["video_90_ngay"]
    sh = vs.get("short") or {}
    gio = [(g, v) for g, v in (sh.get("theo_gio_dang_TW") or {}).items() if v["so_bai"] >= 2 and v["trung_vi"]]
    gio_tot = max(gio, key=lambda x: x[1]["trung_vi"]) if gio else None
    top = sorted((x for kind in vs.values() for x in kind.get("top", [])),
                 key=lambda x: x.get("views_moi_ngay") or 0, reverse=True)[:3]
    return {
        "id": k["id"], "ten": k["ten"], "file": os.path.basename(files[-1]), "tuoi_file_ngay": tuoi_file,
        "ngay_cuoi_co_so_lieu": r["so_ngay"]["ngay_cuoi_co_so_lieu"], "so_ngay_ky": nd,
        "sub": sub, "sub_rong_7_ngay": sub_rong_7, "sub_rong_tuan_tb": round(sub_tuan_tb, 1),
        "sub_can_moi_tuan": round(can_tuan, 1), "kip_500_sub": sub_tuan_tb >= can_tuan,
        "views_ngay_ky": views_ngay, "views_ngay_7": round(s(d7, "views") / (len(d7) or 1), 1),
        "short_pct": short_pct, "short_views_ngay_uoc": round(views_ngay * short_pct / 100, 1),
        "gio_xem_ky": round((r["tong_ky"]["watch_minutes"]["ky_nay"] or 0) / 60, 1),
        "ext_url_views": ext.get("views"), "ext_url_pct": ext.get("ty_le_tren_tong_views_pct"),
        "short_xem_tb_pct": (sh.get("trung_vi_bai_du_7_ngay") or {}).get("avg_view_pct"),
        "gio_dang_tot": f"{gio_tot[0]} (trung vị {f(gio_tot[1]['trung_vi'])} view, {gio_tot[1]['so_bai']} bài)" if gio_tot else None,
        "top": [{"title": x.get("title"), "url": x.get("url"), "views": x.get("views"),
                 "views_moi_ngay": x.get("views_moi_ngay")} for x in top],
        "canh_bao": r.get("data_warning"),
    }


def main():
    hom_nay = date.today()
    out_dir = os.path.join(G, "bao-cao", "tuan", str(hom_nay))
    truoc = sorted(p for p in glob.glob(os.path.join(G, "bao-cao", "tuan", "*", "tom-tat.json"))
                   if os.path.dirname(p) != out_dir)
    cu = {x["id"]: x for x in json.load(open(truoc[-1], encoding="utf-8"))} if truoc else {}
    ks = [mot_kenh(k, acc, hom_nay) for k, acc in kenh_active()]
    tuan_con = (MOC - hom_nay).days / 7

    L = [f"Báo cáo kênh tuần {hom_nay:%d/%m/%Y} (máy tính, chưa qua Claude)",
         f"Mốc bật kiếm tiền 01/03/2027: còn {f(tuan_con, 1)} tuần. Cần 500 sub + 3 triệu view Short/90 ngày"
         f" (= {f(SHORT_VIEW_CAN_NGAY)} view Short/ngày) hoặc 3.000 giờ xem video dài/12 tháng.", ""]
    L.append("TỔNG QUAN")
    for x in ks:
        if "loi" in x:
            L.append(f"- {x['ten']}: {x['loi']}")
            continue
        doi = x["sub"] - cu[x["id"]]["sub"] if x["id"] in cu else None
        L.append(f"- {x['ten']}: {x['sub']} sub" + (f" ({doi:+d} so với tuần trước)" if doi is not None else "")
                 + f", {f(x['views_ngay_7'])} view/ngày (7 ngày cuối), "
                 + ("KỊP" if x["kip_500_sub"] else "KHÔNG KỊP") + " 500 sub")
    for x in ks:
        if "loi" in x:
            continue
        L += ["", f"== {x['ten']} =="]
        if x["tuoi_file_ngay"] > 2:
            L.append(f"CẢNH BÁO: số liệu cũ {x['tuoi_file_ngay']} ngày ({x['file']}), lần kéo YouTube API gần nhất bị lỗi.")
        L.append(f"Số liệu đến {x['ngay_cuoi_co_so_lieu']} (API YouTube trễ 2–3 ngày), kỳ {x['so_ngay_ky']} ngày.")
        L.append(f"Sub: {x['sub']}/500. 7 ngày cuối {x['sub_rong_7_ngay']:+.0f}. Trung bình {f(x['sub_rong_tuan_tb'], 1)}/tuần,"
                 f" cần {f(x['sub_can_moi_tuan'], 1)}/tuần.")
        L.append(f"View: {f(x['views_ngay_ky'])}/ngày cả kỳ, {f(x['views_ngay_7'])}/ngày 7 ngày cuối."
                 f" Short chiếm {f(x['short_pct'], 1)}% (~{f(x['short_views_ngay_uoc'])} view Short/ngày,"
                 f" cần {f(SHORT_VIEW_CAN_NGAY)}).")
        L.append(f"Giờ xem cả kỳ (gồm Short): {f(x['gio_xem_ky'], 1)} giờ.")
        if x["short_xem_tb_pct"] is not None:
            L.append(f"Short: người xem xem trung bình {f(x['short_xem_tb_pct'], 1)}% độ dài (trung vị bài ≥7 ngày).")
        if x["gio_dang_tot"]:
            L.append(f"Giờ đăng Short tốt nhất: {x['gio_dang_tot']}.")
        L.append("Lượt từ ngoài YouTube (TikTok/Facebook/link): "
                 + (f"{f(x['ext_url_views'])} view = {f(x['ext_url_pct'], 1)}%." if x["ext_url_views"] else "0 (mạng phụ chưa kéo được ai sang)."))
        if x["top"]:
            L.append("Top bài (view/ngày, bài ≥7 ngày):")
            L += [f"  {i}. {t['title']} · {f(t['views'])} view · {f(t['views_moi_ngay'], 1)}/ngày · {t['url']}"
                  for i, t in enumerate(x["top"], 1)]
        if x["canh_bao"]:
            L.append(f"Lưu ý số liệu: {x['canh_bao']}")

    p = os.path.join(G, "de-xuat-dang-mo.json")
    if os.path.exists(p):
        dx = json.load(open(p, encoding="utf-8"))
        if dx:
            L += ["", "ĐỀ XUẤT ĐANG THEO DÕI (từ bản phân tích tháng)"]
            L += [f"- [{x.get('kenh')}] {x.get('viec')} · mục tiêu: {x.get('chi_so')} · kiểm ngày {x.get('ngay_kiem')}" for x in dx]
    L += ["", "Phân tích sâu + đề xuất mới: bản tháng (ngày 1 mỗi tháng)."]

    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, "thu.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(ks, open(os.path.join(out_dir, "tom-tat.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = [x for x in ks if "loi" not in x]
    cu_file = [x["ten"] for x in ok if x["tuoi_file_ngay"] > 2]
    kip = sum(x["kip_500_sub"] for x in ok)
    print(os.path.join(out_dir, "thu.txt"))
    print(f"Phân tích kênh: {kip}/{len(ok)} kênh kịp 500 sub; "
          + ", ".join(f"{x['id']} {x['sub']}" for x in ok)
          + (f"; số liệu cũ: {', '.join(cu_file)}" if cu_file else ""))


if __name__ == "__main__":
    main()
