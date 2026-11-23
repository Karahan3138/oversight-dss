"""Deneme verisi: paketteki kodlu formları yapay bir panelle doldurur (Adım 3).

Yapay panel gerçek veri değildir; motoru uçtan uca sınamak içindir. Gruplar arası çatışma
bilerek kurulur: yönetim yüklere, çalışanlar adalete ağırlık verir; hukukçular A1'i ihlal
olarak görür. Bir karar verici bilerek tutarsız BWM yanıtı verir, birinde a_BW iki satırda farklıdır.
"""
import argparse
import glob
import os
import shutil

import numpy as np
from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
BLANK = os.path.join(HERE, "forms", "blank")


def template(name, code):
    """Boş formu açar ve katılımcı kodunu yazar."""
    wb = load_workbook(os.path.join(BLANK, name))
    wb["Yönerge"]["B2"] = code
    return wb
LATENT = {  # 0–10; C7–C10 maliyet (yüksek = büyük yük)
    "A1": [2, 1, 4, 2, 1, 5, 9, 1, 1, 3], "A2": [4, 2, 4, 3, 3, 5, 7, 3, 3, 4],
    "A3": [5, 5, 5, 4, 4, 5, 6, 4, 4, 4], "A4": [6, 7, 6, 6, 6, 6, 5, 5, 5, 5],
    "A5": [7, 8, 6, 8, 8, 7, 3, 7, 6, 6], "A6": [8, 8, 6, 7, 7, 7, 3, 8, 7, 7],
    "A7": [7, 6, 6, 6, 7, 8, 3, 7, 6, 6]}
GROUPS = [  # grup, kademe, boyut ağırlıkları (D1, D2, D3), puan yanlılığı (fayda, maliyet)
    ("Üst yönetim", "Üst yönetim", (.20, .30, .50), (-1.0, +1.5)),
    ("İnsan kaynakları", "Orta kademe yönetici", (.35, .35, .30), (0.0, +0.5)),
    ("Hat yöneticisi", "İlk kademe yönetici", (.25, .30, .45), (-0.5, +1.0)),
    ("Hukuk / uyum", "Uzman", (.35, .45, .20), (0.0, 0.0)),
    ("BT / veri", "Uzman", (.25, .45, .30), (-0.5, +0.5)),
    ("Çalışan veya çalışan temsilcisi", "Çalışan", (.60, .30, .10), (+1.0, -1.0)),
]
LEGAL = {  # (A, R) -> (T, I, F) temel değerleri; R1–R3 AI Act, R4 GDPR, R5 KVKK
    "A1": [(0, .25, 1), (.25, .25, .75), (.5, .25, .25), (0, .25, 1), (0, .25, .75)],
    "A2": [(.5, .5, .25), (.5, .25, .25), (.5, .25, .25), (.5, .75, .25), (.5, .5, .25)],
    "A3": [(.5, .5, .25), (.5, .25, .25), (.75, .25, .25), (.75, .5, .25), (.75, .25, .25)],
    "A4": [(.75, .25, 0), (.75, .25, 0), (.75, .25, 0), (.75, .25, 0), (.75, .25, 0)],
    "A5": [(1, .25, 0), (.75, .25, 0), (.75, .25, 0), (1, .25, 0), (1, 0, 0)],
    "A6": [(1, 0, 0), (1, .25, 0), (1, .25, 0), (1, 0, 0), (1, 0, 0)],
    "A7": [(1, 0, 0), (1, 0, 0), (1, .25, 0), (1, .25, 0), (1, 0, 0)]}
APP = [  # her hukukçu için R1–R5 uygulanabilirlik
    ["Belirsiz", "Muhtemelen evet", "Belirsiz", "Muhtemelen evet", "Kesinlikle evet"],
    ["Muhtemelen hayır", "Belirsiz", "Muhtemelen hayır", "Muhtemelen evet", "Kesinlikle evet"],
    ["Muhtemelen evet", "Muhtemelen evet", "Belirsiz", "Kesinlikle evet", "Kesinlikle evet"]]
STEPS = [0, .25, .5, .75, 1]
# gruba özgü düzen tercihleri: (fayda ölçütlerine ek, maliyet ölçütlerine ek)
TILT = {"Çalışan veya çalışan temsilcisi": {"A6": (+2.5, -2.0), "A5": (+1.0, 0.0)},
        "Üst yönetim": {"A6": (-1.5, +2.0), "A7": (+0.5, -0.5)},
        "Hat yöneticisi": {"A6": (-1.0, +1.5)},
        "BT / veri": {"A7": (+1.0, 0.0)}}


def snap(v):
    return min(STEPS, key=lambda s: abs(s - v))


def bwm_answers(w, rng, noise=0.0):
    w = np.asarray(w, float)
    B, W = int(np.argmax(w)), int(np.argmin(w))
    a_bw = int(np.clip(round(w[B] / w[W]), 2, 9))
    aW = np.clip(np.round(w / w[W] * np.exp(rng.normal(0, noise, len(w)))), 1, a_bw).astype(int)
    aB = np.clip(np.round(a_bw / aW * np.exp(rng.normal(0, noise, len(w)))), 1, 9).astype(int)
    aB[B], aW[W], aB[W], aW[B] = 1, 1, a_bw, a_bw
    return B, W, aB, aW


def fill(out_dir, seed=4, n_experts=15, n_lawyers=3, dm_per_group=3):
    rng = np.random.default_rng(seed)
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    # ---- uzmanlar
    for e in range(n_experts):
        p = f"U{e + 1:02d}_Uzman_Formu.xlsx"
        wb = template("Uzman_IcerikGecerligi_Formu.xlsx", p[:3]); ws = wb["Form"]
        ws["E2"], ws["E3"], ws["E4"] = "İnsan kaynakları yönetimi", int(rng.integers(5, 25)), "Üniversite"
        for r in range(8, ws.max_row + 1):
            if isinstance(ws.cell(r, 1).value, int) and ws.cell(r, 3).value:
                q = ws.cell(r, 3).value
                pr = .55 if q in ("A3", "C9") else .9           # A3 ve C9 sınırda
                ws.cell(r, 6).value = rng.choice(["Gerekli", "Yararlı ama gerekli değil", "Gereksiz"], p=[pr, (1 - pr) * .8, (1 - pr) * .2])
                ws.cell(r, 7).value = "Evet"
        wb.save(f"{out_dir}/{os.path.basename(p)}")
    # ---- hukukçular
    for h in range(n_lawyers):
        p = f"H{h + 1:02d}_Hukukcu_Formu.xlsx"
        wb = template("Hukukcu_Formu.xlsx", p[:3])
        u = wb["Uygulanabilirlik"]
        for r in range(2, 7):
            u.cell(r, 3).value = APP[h][r - 2]
        d = wb["Değerlendirme"]
        for r in range(3, d.max_row + 1):
            if not isinstance(d.cell(r, 1).value, int):
                continue
            a, q = d.cell(r, 2).value.split()[0], d.cell(r, 3).value.split()[0]
            base = LEGAL[a][int(q[1]) - 1]
            for j, v in zip((4, 5, 6), base):
                d.cell(r, j).value = snap(v + rng.choice([-.25, 0, 0, 0, .25]))
        wb.save(f"{out_dir}/{os.path.basename(p)}")
    # ---- karar vericiler
    files = [f"K{i:02d}_Karar_Verici_Formu.xlsx" for i in range(1, 1 + dm_per_group * len(GROUPS))]
    k = 0
    for g_name, level, dimw, (bb, bc) in GROUPS:
        for _ in range(dm_per_group):
            p = files[k]; k += 1
            wb = template("Karar_Verici_Formu.xlsx", p[:3])
            b = wb["Bilgiler"]; b["B1"], b["B2"], b["B3"] = g_name, level, "3–5 yıl"
            o = wb["Önem"]
            blocks = [r for r in range(1, o.max_row + 1) if str(o.cell(r, 1).value).startswith("Blok")]
            for r in blocks:
                hdr = r + 3
                elems = [o.cell(hdr, j).value for j in range(2, o.max_column + 1) if o.cell(hdr, j).value]
                if "Boyutlar" in o.cell(r, 1).value:
                    w = rng.dirichlet(80 * np.array(dimw))
                else:
                    w = rng.dirichlet(np.full(len(elems), 3.0))
                B, W, aB, aW = bwm_answers(w, rng, noise=0.6 if k == 5 else 0.1)
                o.cell(r + 1, 2).value, o.cell(r + 2, 2).value = elems[B], elems[W]
                if k == 8 and "Boyutlar" in o.cell(r, 1).value:
                    aW[B] = min(9, aB[W] + 1)                       # a_BW iki satırda farklı
                for j in range(len(elems)):
                    o.cell(hdr + 1, 2 + j).value, o.cell(hdr + 2, 2 + j).value = int(aB[j]), int(aW[j])
            v = wb["Değerlendirme"]
            for r in range(4, 11):
                a = v.cell(r, 1).value.split()[0]
                for j in range(10):
                    tb, tc = TILT.get(g_name, {}).get(a, (0.0, 0.0))
                    bias = (bb + tb) if j < 6 else (bc + tc)
                    v.cell(r, 2 + j).value = int(np.clip(round(LATENT[a][j] + bias + rng.normal(0, 1.0)), 0, 10))
            wb.save(f"{out_dir}/{os.path.basename(p)}")
    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "test_data", "forms"))
    ap.add_argument("--seed", type=int, default=4)
    a = ap.parse_args()
    print(fill(a.out, a.seed))
