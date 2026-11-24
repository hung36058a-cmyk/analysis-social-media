"""Gửi phần "## Bản gửi" (tên cũ: "## Bản Telegram") của ban-cuoi.md qua Gmail, CHỈ KHI đã qua 2 vòng phản biện.

Dùng:
    python gui_bao_cao.py --hash <file>        # in SHA256 của file (ghi vào đầu file phản biện)
    python gui_bao_cao.py --kiem <R>           # chỉ kiểm cổng, không gửi
    python gui_bao_cao.py <R>                  # kiểm cổng rồi gửi
    python gui_bao_cao.py <R> --gui-lai        # gửi lại dù đã gửi trước đó

Cổng (thiếu 1 điều là KHÔNG gửi):
  1. <R>\\ban-cuoi.md tồn tại và có mục "## Bản gửi" (hoặc "## Bản Telegram") không rỗng.
  2. File phản biện mới nhất của MỖI vòng (<R>\\phan-bien\\v1-lan<N>.md, v2-lan<N>.md) có dòng
     "KET_LUAN: DAT" và dòng "SHA256: <mã>" trùng SHA256 của ban-cuoi.md
     (tức là ban-cuoi.md giống TỪNG CHỮ với bản mà cả 2 vòng đã cho DAT).
  3. Chưa gửi lần nào (<R>\\da-gui.txt chưa có), trừ khi có --gui-lai.

Gửi bằng gmail.py của repo đăng MXH (auto-upload-social-media): E:\\01_YouTube\\00_Dung-chung\\he-thong-mxh\\chung.
"""
import glob
import hashlib
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CHUNG = r"E:\01_YouTube\00_Dung-chung\he-thong-mxh\chung"     # gmail.py dung chung (1 ban duy nhat)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def latest(R, vong):
    files = glob.glob(os.path.join(R, "phan-bien", f"v{vong}-lan*.md"))
    nums = [(int(m.group(1)), f) for f in files if (m := re.search(r"lan(\d+)\.md$", f))]
    return max(nums)[1] if nums else None


def kiem_cong(R):
    """Trả (đoạn gửi, None) nếu đạt, hoặc (None, lý do)."""
    cuoi = os.path.join(R, "ban-cuoi.md")
    if not os.path.exists(cuoi):
        return None, "CHUA_CO ban-cuoi.md"
    h = sha(cuoi)
    for vong in (1, 2):
        f = latest(R, vong)
        if not f:
            return None, f"THIEU phản biện vòng {vong}"
        t = open(f, encoding="utf-8").read()
        if not re.search(r"^KET_LUAN:\s*DAT\s*$", t, re.M):
            return None, f"VONG_{vong}_CHUA_DAT ({os.path.basename(f)})"
        m = re.search(r"SHA256:\s*([0-9a-f]{64})", t)
        if not m or m.group(1) != h:
            return None, f"VONG_{vong}_KIEM_BAN_KHAC: ban-cuoi.md không trùng bản vòng {vong} đã kiểm"
    text = open(cuoi, encoding="utf-8").read()
    m = re.search(r"^## Bản (?:gửi|Telegram)\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    body = m.group(1).strip().strip("`").strip() if m else ""
    if not body:
        return None, "THIEU mục '## Bản gửi' trong ban-cuoi.md"
    return body, None


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "--hash":
        print(sha(a[1]))
        return
    only_check = a[0] == "--kiem"
    R = a[1] if only_check else a[0]
    body, err = kiem_cong(R)
    if err:
        sys.exit("KHONG_GUI: " + err)
    if only_check:
        print("CONG_DAT")
        return
    marker = os.path.join(R, "da-gui.txt")
    if os.path.exists(marker) and "--gui-lai" not in a:
        sys.exit("DA_GUI_TRUOC_DO (thêm --gui-lai nếu muốn gửi lại)")
    sys.path.insert(0, CHUNG)
    import gmail
    kenh = os.path.basename(os.path.dirname(os.path.normpath(R)))
    ngay = os.path.basename(os.path.normpath(R))
    da = gmail.gui(f"[MXH] Phân tích kênh {kenh} · {ngay} (đã qua 2 vòng phản biện)", body)
    with open(marker, "w", encoding="utf-8") as f:     # thu da vao hang cho -> khong gui lai lan 2
        f.write(f"{datetime.now().isoformat(timespec='seconds')} qua Gmail" + ("" if da else " (hang cho)") + "\n")
    print("DA_GUI Gmail" if da else "CHO_GUI: thư vào hàng chờ Gmail, tự gửi bù lần kế (xem he-thong-mxh/chung/hop-thu-cho/nhat-ky-gmail.log)")


if __name__ == "__main__":
    main()
