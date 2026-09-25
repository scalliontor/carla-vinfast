#!/usr/bin/env python
"""
Đối chiếu footprint OSM với ảnh vệ tinh — chấm điểm bằng số, không bằng mắt
===========================================================================

VÌ SAO CẦN CÔNG CỤ NÀY
    Nhìn ảnh phủ mờ bằng mắt rất dễ kết luận sai. Nền ảnh bị làm nhạt để thấy
    footprint, nhưng chính việc đó khiến map trông "thưa" và "lệch" dù dữ liệu
    tốt. Phiên trước đã suýt kết luận nhầm theo hướng này.

    Script tách câu hỏi mơ hồ "dữ liệu có tốt không" thành HAI câu hỏi đo được:

    1. ĐÚNG CHỖ chưa?  (alignment)
       Footprint có nằm đè lên mái nhà thật không, hay lệch đi vài chục mét?
       Đo bằng cách quét thử mọi phép dịch chuyển (dx, dy) rồi xem phép nào
       làm footprint trùng mái nhất. Nếu dữ liệu lệch hệ thống, sẽ có một
       (dx, dy) nổi bật hẳn. Nếu điểm cao nhất nằm ngay cạnh (0,0) thì không
       có độ lệch — dữ liệu đã đúng chỗ.

    2. ĐỦ chưa?  (completeness)
       Ngoài kia còn mái nhà nào mà OSM không có? Đếm các khối sáng, đặc,
       không phải cây, nằm ngoài mọi footprint.

    Hai lỗi này dẫn tới hai hướng xử lý HOÀN TOÀN KHÁC NHAU:
       lệch  -> dữ liệu hỏng, phải đổi vùng
       thiếu -> dữ liệu đúng nhưng mỏng, chỉ cần vẽ bổ sung

CÁCH NHẬN BIẾT MÁI NHÀ TRONG ẢNH
    Không dùng AI. Chỉ cần hai đại lượng, và NGƯỠNG PHẢI ĐO CHỨ ĐỪNG ĐOÁN:

       độ sáng (lum)        = trung bình R,G,B    -> mái sáng, đường/bóng tối
       độ trội xanh (ge)    = G - (R+B)/2         -> cây cối cao, mái thấp

    Ảnh Esri vùng này ám xanh, ge dương ở mọi nơi. Lần chạy đầu tôi đoán
    ngưỡng ge < 3 và chỉ nhận ra 0,1 ha mái trên toàn khung — sai hoàn toàn.
    Hàm do_nguong() bên dưới tự đo phân vị ngay trong/ngoài footprint đã biết
    để chọn ngưỡng, nên đổi sang ảnh khác vẫn chạy đúng.

DỮ LIỆU VÀO
    - thư mục tile XYZ (kèm range.txt ghi x0,y0,x1,y1) tải từ Esri World Imagery
    - file .osm cùng khu vực

CHẠY
    .venv-sr\\Scripts\\python.exe my_client\\doi_chieu_vetinh.py ^
        evidence\\task3\\tiles  osm\\vinuni_campus.osm  out\\doi_chieu
"""

import os
import sys
import math
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


TILE = 256          # tile XYZ chuẩn 256x256
ZOOM = 18           # mức zoom đã tải; z18 ~ 0,56 m/pixel ở vĩ độ Hà Nội


# ---------------------------------------------------------------------------
# 1. GHÉP TILE VÀ QUY ĐỔI TOẠ ĐỘ
# ---------------------------------------------------------------------------

class KhungAnh:
    """Ghép các tile thành một ảnh lớn và quy đổi lon/lat sang pixel trong đó.

    Cả ảnh vệ tinh lẫn footprint OSM phải nằm trong CÙNG một hệ pixel thì mới
    so sánh được — lớp này giữ phép quy đổi đó ở một chỗ duy nhất.
    """

    def __init__(self, thu_muc_tile, zoom=ZOOM):
        self.dir = thu_muc_tile
        self.n = 2 ** zoom

        # range.txt do script tải tile ghi ra: "x0=... y0=... x1=... y1=..."
        with open(os.path.join(thu_muc_tile, "range.txt")) as f:
            r = dict(kv.split("=") for kv in f.read().split())
        self.x0, self.y0 = int(r["x0"]), int(r["y0"])
        self.x1, self.y1 = int(r["x1"]), int(r["y1"])

        self.W = (self.x1 - self.x0 + 1) * TILE
        self.H = (self.y1 - self.y0 + 1) * TILE

        # Số mét ứng với 1 pixel. Web Mercator giãn theo vĩ độ nên phải nhân cos.
        lat_giua = self.pixel2lat(self.H / 2.0)
        self.mpp = 156543.03392 * math.cos(math.radians(lat_giua)) / self.n

    def anh(self):
        im = Image.new("RGB", (self.W, self.H))
        for tx in range(self.x0, self.x1 + 1):
            for ty in range(self.y0, self.y1 + 1):
                p = os.path.join(self.dir, "t_%d_%d.jpg" % (tx, ty))
                if os.path.exists(p):          # tile lỗi mạng -> để đen, lọc sau
                    im.paste(Image.open(p), ((tx - self.x0) * TILE,
                                             (ty - self.y0) * TILE))
        return im

    def lonlat2px(self, lon, lat):
        """Web Mercator xuôi: kinh/vĩ độ -> pixel trong khung ảnh đã ghép."""
        x = (lon + 180.0) / 360.0 * self.n
        s = math.sin(math.radians(lat))
        y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * self.n
        return (x - self.x0) * TILE, (y - self.y0) * TILE

    def pixel2lat(self, py):
        """Mercator ngược — chỉ dùng để biết vĩ độ giữa khung mà tính mpp."""
        y = self.y0 + py / float(TILE)
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / self.n))))


def doc_footprint(duong_dan_osm, khung):
    """Đọc mọi way có thẻ building, trả về danh sách đa giác toạ độ pixel."""
    root = ET.parse(duong_dan_osm).getroot()
    nodes = {n.get("id"): (float(n.get("lon")), float(n.get("lat")))
             for n in root.iter("node")}

    polys, ten = [], []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        if "building" not in tags:
            continue
        refs = [nd.get("ref") for nd in w.findall("nd")]
        pts = [khung.lonlat2px(*nodes[i]) for i in refs if i in nodes]
        if len(pts) >= 4:                      # vòng kín cần tối thiểu 4 điểm
            polys.append(np.array(pts))
            ten.append(tags.get("name", ""))
    return polys, ten


def to_mask(polys, W, H, dx=0, dy=0):
    """Tô đặc các đa giác thành mặt nạ nhị phân, có thể dịch đi (dx, dy)."""
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        d.polygon([(x + dx, y + dy) for x, y in p], fill=255)
    return np.asarray(m) > 0


# ---------------------------------------------------------------------------
# 2. NHẬN BIẾT MÁI NHÀ — NGƯỠNG ĐO TỪ CHÍNH ẢNH
# ---------------------------------------------------------------------------

def do_nguong(lum, ge, trong_fp, hop_le):
    """Tự chọn ngưỡng sáng/xanh bằng cách so phân bố trong và ngoài footprint.

    Lấy phân vị 25 của độ sáng trong footprint (mái tối nhất vẫn tính là mái)
    và phân vị 75 của độ trội xanh (mái xanh rêu vẫn tính là mái). Cách này
    tránh được việc đoán ngưỡng cố định cho từng ảnh.
    """
    ngoai = hop_le & ~trong_fp
    nguong_lum = float(np.percentile(lum[trong_fp], 25))
    nguong_ge = float(np.percentile(ge[trong_fp], 75))
    print("  ngưỡng tự đo: độ sáng > %.0f, độ trội xanh < %.1f" %
          (nguong_lum, nguong_ge))
    print("  (trong footprint sáng TB %.0f — ngoài %.0f)" %
          (lum[trong_fp].mean(), lum[ngoai].mean()))
    return nguong_lum, nguong_ge


def mat_na_mai(img, nguong_lum, nguong_ge, hop_le):
    lum = img.mean(2)
    ge = img[..., 1] - (img[..., 0] + img[..., 2]) / 2.0
    mai = (lum > nguong_lum) & (ge < nguong_ge) & hop_le
    # Lọc trung vị xoá đốm lẻ tẻ (xe hơi, vạch kẻ) mà giữ nguyên cạnh mái.
    return np.asarray(Image.fromarray((mai * 255).astype(np.uint8))
                      .filter(ImageFilter.MedianFilter(5))) > 128


# ---------------------------------------------------------------------------
# 3. CÂU HỎI 1 — FOOTPRINT CÓ ĐÚNG CHỖ KHÔNG?
# ---------------------------------------------------------------------------

def quet_do_lech(diem, polys, khung, bien=30, buoc=2):
    """Thử dịch footprint đi mọi hướng, xem hướng nào trùng mái nhiều nhất.

    Ý tưởng: nếu dữ liệu OSM bị lệch hệ thống (sai gốc toạ độ, sai phép chiếu)
    thì tồn tại đúng một (dx, dy) khác 0 làm điểm trùng tăng vọt. Còn nếu điểm
    cao nhất chỉ nhỉnh hơn (0,0) một chút và nằm sát bên, đó chỉ là nhiễu căn
    ảnh của chính Esri — coi như không lệch.
    """
    ket = []
    for dy in range(-bien, bien + 1, buoc):
        for dx in range(-bien, bien + 1, buoc):
            m = to_mask(polys, khung.W, khung.H, dx, dy)
            ket.append((float(diem[m].mean()), dx, dy))
    ket.sort(reverse=True)
    goc = [k for k in ket if k[1] == 0 and k[2] == 0][0]
    return ket[0], goc


def cham_tung_toa(diem, polys, ten, khung):
    """Mỗi toà: điểm trong lòng trừ điểm vành ngoài.

    Footprint đặt đúng mái -> trong lòng sáng hơn hẳn vành ngoài (sân, cây).
    Lưu ý: toà mái sẫm màu sẽ bị chấm thấp oan, nên phải xem ảnh cắt để xác
    nhận trước khi kết luận là lệch.
    """
    rows = []
    for p, nm in zip(polys, ten):
        trong = to_mask([p], khung.W, khung.H)
        tam = p.mean(0)
        vanh = to_mask([(p - tam) * 1.8 + tam], khung.W, khung.H) & ~trong
        if trong.sum() < 20 or vanh.sum() < 20:
            continue
        rows.append((float(diem[trong].mean() - diem[vanh].mean()),
                     trong.sum() * khung.mpp ** 2, nm))
    rows.sort(reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 4. CÂU HỎI 2 — CÒN THIẾU TOÀ NÀO?
# ---------------------------------------------------------------------------

def tim_nha_thieu(mai, fp, khung, dien_tich_min=60):
    """Khối mái nằm ngoài mọi footprint, có hình dáng giống toà nhà.

    Ba bộ lọc, đều cần thiết:
       diện tích  — bỏ mẩu vụn vài pixel
       độ đặc     — lối đi bê tông sáng nhưng rỗng trong hộp bao, loại được
       tỉ lệ cạnh — vệt đường dài ngoằng không phải nhà
    """
    # Nới footprint ra vài pixel: mái lệch nhẹ hay bóng đổ vẫn coi là "đã có".
    fp_no = np.asarray(Image.fromarray((fp * 255).astype(np.uint8))
                       .filter(ImageFilter.MaxFilter(9))) > 128
    ung_vien = mai & ~fp_no

    # Gán nhãn liên thông bằng BFS lặp (tránh phụ thuộc scipy, và tránh đệ quy
    # sâu làm tràn stack trên khối lớn).
    da_xet = np.zeros(ung_vien.shape, bool)
    khoi = []
    ys, xs = np.nonzero(ung_vien)
    for sy, sx in zip(ys, xs):
        if da_xet[sy, sx]:
            continue
        stack, pix = [(sy, sx)], []
        da_xet[sy, sx] = True
        while stack:
            y, x = stack.pop()
            pix.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if (0 <= ny < ung_vien.shape[0] and 0 <= nx < ung_vien.shape[1]
                        and ung_vien[ny, nx] and not da_xet[ny, nx]):
                    da_xet[ny, nx] = True
                    stack.append((ny, nx))
        khoi.append(np.array(pix))

    giu, mask = [], np.zeros(ung_vien.shape, bool)
    for b in khoi:
        dt = len(b) * khung.mpp ** 2
        if dt < dien_tich_min:
            continue
        h = b[:, 0].ptp() + 1
        w = b[:, 1].ptp() + 1
        if len(b) / float(h * w) < 0.35:                 # rỗng -> lối đi
            continue
        if max(h, w) / max(1.0, min(h, w)) > 6:          # dài ngoẵng -> đường
            continue
        giu.append((dt, b[:, 1].mean(), b[:, 0].mean()))
        mask[b[:, 0], b[:, 1]] = True
    giu.sort(reverse=True)
    return giu, mask


# ---------------------------------------------------------------------------
# 5. ẢNH KẾT QUẢ
# ---------------------------------------------------------------------------

def ve_vien(sat, polys, duong_dan):
    """Ảnh vệ tinh NGUYÊN ĐỘ SÁNG, chỉ kẻ viền footprint.

    Đây là cách xem đáng tin nhất: phủ mờ nền để thấy footprint chính là thứ
    làm người xem tưởng dữ liệu kém.
    """
    out = sat.convert("RGB").copy()
    d = ImageDraw.Draw(out)
    for p in polys:
        d.line([tuple(x) for x in p] + [tuple(p[0])], fill=(255, 40, 0), width=3)
    out.save(duong_dan)


def ve_do_phu(sat, fp, mask_thieu, duong_dan):
    """Xanh = OSM đã có, Đỏ = mái nhà thật còn thiếu."""
    out = np.asarray(sat).astype(np.float32).copy()
    out[fp] = out[fp] * .40 + np.array([0, 255, 90]) * .60
    out[mask_thieu] = out[mask_thieu] * .35 + np.array([255, 0, 40]) * .65
    Image.fromarray(out.astype(np.uint8)).save(duong_dan)


# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    thu_muc_tile, duong_dan_osm, thu_muc_ra = sys.argv[1:4]
    os.makedirs(thu_muc_ra, exist_ok=True)

    khung = KhungAnh(thu_muc_tile)
    sat = khung.anh()
    img = np.asarray(sat).astype(np.float32)
    lum = img.mean(2)
    ge = img[..., 1] - (img[..., 0] + img[..., 2]) / 2.0
    hop_le = lum > 12                       # loại vùng đen do tile thiếu

    polys, ten = doc_footprint(duong_dan_osm, khung)
    fp = to_mask(polys, khung.W, khung.H)
    px2 = khung.mpp ** 2
    print("Khung %dx%d px, %.2f m/px — %.1f ha" %
          (khung.W, khung.H, khung.mpp, hop_le.sum() * px2 / 1e4))
    print("Đọc được %d footprint, tổng %.2f ha\n" % (len(polys), fp.sum() * px2 / 1e4))

    print("[1] FOOTPRINT CÓ ĐÚNG CHỖ KHÔNG?")
    nguong_lum, nguong_ge = do_nguong(lum, ge, fp & hop_le, hop_le)
    # Điểm liên tục (không phải nhị phân) cho phép quét dịch chuyển mượt hơn.
    diem = np.clip((lum - nguong_lum) / 60.0 - (ge - nguong_ge) / 12.0, -2, 3)

    tot, goc = quet_do_lech(diem, polys, khung)
    lech_m = math.hypot(tot[1], tot[2]) * khung.mpp
    print("  không dịch : %.3f" % goc[0])
    print("  tốt nhất   : %.3f tại dx=%+d dy=%+d  (%.1f m)" %
          (tot[0], tot[1], tot[2], lech_m))
    print("  -> %s" % ("KHÔNG lệch hệ thống — dữ liệu đúng chỗ"
                       if lech_m < 5 and tot[0] - goc[0] < 0.1
                       else "CÓ lệch hệ thống, cần xem lại phép chiếu"))

    rows = cham_tung_toa(diem, polys, ten, khung)
    kho = sum(1 for d, a, n in rows if d > 0.25)
    xau = sum(1 for d, a, n in rows if d < 0.0)
    print("  từng toà: %d/%d trùng mái rõ (%.0f%%), %d không trùng (%.0f%%)" %
          (kho, len(rows), 100.0 * kho / len(rows), xau, 100.0 * xau / len(rows)))
    print("  lệch nhất:", ", ".join("%s %+.2f" % (n or "(không tên)", d)
                                    for d, a, n in rows[-3:]))

    print("\n[2] CÒN THIẾU TOÀ NÀO?")
    mai = mat_na_mai(img, nguong_lum, nguong_ge, hop_le)
    thieu, mask_thieu = tim_nha_thieu(mai, fp, khung)
    print("  mái nhận diện được : %.2f ha" % (mai.sum() * px2 / 1e4))
    print("  khối giống nhà mà OSM thiếu: %d, tổng %.2f ha" %
          (len(thieu), sum(t[0] for t in thieu) / 1e4))
    print("  lớn nhất:", ", ".join("%.0f m2" % t[0] for t in thieu[:5]))

    ve_vien(sat, polys, os.path.join(thu_muc_ra, "vien_footprint.png"))
    ve_do_phu(sat, fp, mask_thieu, os.path.join(thu_muc_ra, "do_phu.png"))
    print("\n-> %s\\vien_footprint.png  (xem ở đây để tự xác nhận bằng mắt)"
          % thu_muc_ra)
    print("-> %s\\do_phu.png           (xanh = đã có, đỏ = còn thiếu)"
          % thu_muc_ra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
