"""Doldurulmuş formları okur ve doğrular (uzman, hukukçu, karar verici).

Form düzeni scripts/build_forms.py ve scripts/build_cvr.py ile üretilen dosyalara göredir.
Örnek satırlar okunmaz. Her sorun `issues` listesine yazılır; okuma durmaz.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field

import numpy as np
from openpyxl import load_workbook


def _code(label):
    """'C1 Usul adaleti' -> 'C1'."""
    return str(label).split()[0] if label is not None else None


def _participant(wb, path):
    v = wb["Yönerge"]["B2"].value
    if v and v != "[KOD]":
        return str(v).strip()
    return os.path.basename(path).split("_")[0]


# ------------------------------------------------------------------- uzman formu
@dataclass
class ExpertForm:
    code: str
    field: str | None
    years: int | None
    institution: str | None
    ratings: dict          # öğe kodu -> değerlendirme
    clarity: dict          # öğe kodu -> Evet/Hayır
    comments: dict         # öğe kodu -> yorum
    suggestions: list      # eksik öğe önerileri
    issues: list = field(default_factory=list)


def read_expert(path) -> ExpertForm:
    wb = load_workbook(path, data_only=True)
    ws = wb["Form"]
    code = _participant(wb, path)
    f = ExpertForm(code, ws["E2"].value, ws["E3"].value, ws["E4"].value, {}, {}, {}, [])
    sugg_start = None
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if a == "Eksik gördüğünüz alternatif ya da ölçütler":
            sugg_start = r + 2
            break
        if isinstance(a, int) and ws.cell(r, 3).value:
            q = str(ws.cell(r, 3).value).strip()
            f.ratings[q] = ws.cell(r, 6).value
            f.clarity[q] = ws.cell(r, 7).value
            f.comments[q] = ws.cell(r, 8).value
            if not ws.cell(r, 6).value:
                f.issues.append(f"{code}: {q} için değerlendirme boş")
    if sugg_start:
        for r in range(sugg_start, ws.max_row + 1):
            vals = [ws.cell(r, j).value for j in range(2, 7)]
            if any(vals):
                f.suggestions.append(dict(type=vals[0], item=vals[2], definition=vals[3], why=vals[4]))
    return f


# ----------------------------------------------------------------- hukukçu formu
@dataclass
class LawyerForm:
    code: str
    applicability: dict    # R kodu -> yanıt
    T: dict                # (A, R) -> değer
    I: dict
    F: dict
    reasons: dict
    issues: list = field(default_factory=list)


def read_lawyer(path) -> LawyerForm:
    wb = load_workbook(path, data_only=True)
    code = _participant(wb, path)
    f = LawyerForm(code, {}, {}, {}, {}, {})
    u = wb["Uygulanabilirlik"]
    for r in range(2, u.max_row + 1):
        q = u.cell(r, 1).value
        if q:
            f.applicability[str(q)] = u.cell(r, 3).value
            if not u.cell(r, 3).value:
                f.issues.append(f"{code}: {q} uygulanabilirlik yanıtı boş")
    d = wb["Değerlendirme"]
    for r in range(3, d.max_row + 1):
        if not isinstance(d.cell(r, 1).value, int):
            continue
        a, q = _code(d.cell(r, 2).value), _code(d.cell(r, 3).value)
        for j, store in ((4, f.T), (5, f.I), (6, f.F)):
            v = d.cell(r, j).value
            store[(a, q)] = float(v) if v is not None and v != "" else np.nan
        f.reasons[(a, q)] = d.cell(r, 7).value
        if any(np.isnan(s[(a, q)]) for s in (f.T, f.I, f.F)):
            f.issues.append(f"{code}: {a}–{q} için T, I ya da F boş")
    return f


# ----------------------------------------------------------- karar verici formu
@dataclass
class DMForm:
    code: str
    group: str | None
    level: str | None
    tenure: str | None
    blocks: dict           # blok anahtarı ('dim' ya da D kodu) -> dict(elems, best, worst, a_B, a_W)
    ratings: dict          # (A, C) -> puan
    issues: list = field(default_factory=list)


def read_dm(path) -> DMForm:
    wb = load_workbook(path, data_only=True)
    code = _participant(wb, path)
    b = wb["Bilgiler"]
    f = DMForm(code, b["B1"].value, b["B2"].value, b["B3"].value, {}, {})
    for lab, v in (("grup", f.group), ("kademe", f.level)):
        if not v:
            f.issues.append(f"{code}: {lab} boş")
    o = wb["Önem"]
    for r in range(1, o.max_row + 1):
        title = o.cell(r, 1).value
        if not (isinstance(title, str) and title.startswith("Blok")):
            continue
        hdr = r + 3
        elems = [_code(o.cell(hdr, j).value) for j in range(2, o.max_column + 1) if o.cell(hdr, j).value]
        key = "dim" if "Boyutlar" in title else re.search(r"Blok: (\S+)", title).group(1)
        best, worst = _code(o.cell(r + 1, 2).value), _code(o.cell(r + 2, 2).value)
        aB = [o.cell(hdr + 1, j).value for j in range(2, 2 + len(elems))]
        aW = [o.cell(hdr + 2, j).value for j in range(2, 2 + len(elems))]
        blk = dict(elems=elems, best=best, worst=worst, a_B=aB, a_W=aW, ok=True)
        probs = []
        if best not in elems or worst not in elems:
            probs.append("en önemli/en önemsiz seçilmemiş")
        elif best == worst:
            probs.append("en önemli ve en önemsiz aynı")
        if any(not isinstance(v, (int, float)) or not 1 <= v <= 9 for v in aB + aW):
            probs.append("1–9 dışında ya da boş değer")
        if not probs:
            iB, iW = elems.index(best), elems.index(worst)
            if aB[iB] != 1:
                probs.append("en önemlinin kendisi için 1 yazılmamış")
            if aW[iW] != 1:
                probs.append("en önemsizin kendisi için 1 yazılmamış")
        if probs:
            blk["ok"] = False
            f.issues.append(f"{code}: {key} bloğu kullanılamaz ({'; '.join(probs)})")
        else:
            blk["a_B"], blk["a_W"] = np.array(aB, float), np.array(aW, float)
            if aB[elems.index(worst)] != aW[elems.index(best)]:
                f.issues.append(f"{code}: {key} bloğunda a_BW iki satırda farklı")
        f.blocks[key] = blk
    v = wb["Değerlendirme"]
    crit = [_code(v.cell(2, j).value) for j in range(2, v.max_column + 1)
            if v.cell(2, j).value and str(v.cell(2, j).value).startswith("C")]
    for r in range(4, v.max_row + 1):
        a = _code(v.cell(r, 1).value)
        if not a or not a.startswith("A"):
            continue
        for j, c in enumerate(crit, 2):
            val = v.cell(r, j).value
            ok = isinstance(val, (int, float)) and float(val).is_integer() and 0 <= val <= 10
            f.ratings[(a, c)] = int(val) if ok else None
            if not ok:
                f.issues.append(f"{code}: {a}–{c} puanı eksik ya da geçersiz")
    return f


def read_folder(folder):
    """Klasördeki U*, H* ve K* dosyalarını okur (alt klasörler dahil)."""
    files = sorted(glob.glob(os.path.join(folder, "**", "*.xlsx"), recursive=True))
    out = dict(experts=[], lawyers=[], dms=[])
    for p in files:
        name = os.path.basename(p)
        if name.startswith("~$"):
            continue
        if re.match(r"U\d+_", name):
            out["experts"].append(read_expert(p))
        elif re.match(r"H\d+_", name):
            out["lawyers"].append(read_lawyer(p))
        elif re.match(r"K\d+_", name):
            out["dms"].append(read_dm(p))
    return out
