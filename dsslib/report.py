"""Sonuçları Excel raporu ve JSON özeti olarak yazar."""
from __future__ import annotations

import json

import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L

F = "Arial"
BODY, BOLD, TITLE = Font(name=F, size=10), Font(name=F, size=10, bold=True), Font(name=F, size=12, bold=True)
HEAD_FILL = PatternFill("solid", fgColor="D9E1F2")
TOP_FILL = PatternFill("solid", fgColor="E2EFDA")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")


def _v(x):
    if isinstance(x, (np.floating,)):
        x = float(x)
    if isinstance(x, (np.integer,)):
        x = int(x)
    if isinstance(x, (np.bool_,)):
        x = bool(x)
    if isinstance(x, bool):
        return "Evet" if x else "Hayır"
    if isinstance(x, float) and np.isnan(x):
        return None
    return x


def table(ws, r, headers, rows, fmt="0.000", widths=None, highlight=None):
    for j, h in enumerate(headers, 1):
        c = ws.cell(r, j, h); c.font, c.fill, c.border, c.alignment = BOLD, HEAD_FILL, BORDER, WRAP
    for i, row in enumerate(rows, r + 1):
        for j, v in enumerate(row, 1):
            c = ws.cell(i, j, _v(v)); c.font, c.border = BODY, BORDER
            if isinstance(c.value, float):
                c.number_format = fmt
            if highlight is not None and highlight(i - r - 1):
                c.fill = TOP_FILL
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[L(j)].width = max(ws.column_dimensions[L(j)].width or 0, w)
    return r + len(rows) + 2


def title(ws, r, text, note=None):
    ws.cell(r, 1, text).font = TITLE
    if note:
        c = ws.cell(r + 1, 1, note); c.font = Font(name=F, size=9, italic=True, color="595959")
        return r + 3
    return r + 2


def write_report(path, case, cfg, res, stage1_rows=None, experts=None):
    alts, crits, reqs = case.alts, case.crits, case.reqs
    name = {a["code"]: a["name"] for a in cfg["alternatives"]}
    cname = {c["code"]: c["name"] for c in cfg["criteria"]}
    b = res["base"]
    legal = b["legal"]
    P = cfg["parameters"]
    wb = Workbook()

    # ------------------------------------------------------------------ Özet
    ws = wb.active; ws.title = "Özet"
    ws.column_dimensions["A"].width = 34
    r = title(ws, 1, "Öneri: insan denetimi düzenlerinin sıralaması",
              f"Taban ayarlar: τ_F = {P['tau_F']}, θ = {P['theta']}, γ = {P['gamma_percentile']}. yüzdelik, δ = {P['delta']}. "
              f"Karar verici K = {len(case.dms)}, hukukçu H = {len(case.lawyers)}.")
    V = b["V"]
    order = sorted(range(len(alts)), key=lambda i: (-(V[i]) if not np.isnan(V[i]) else 9e9))
    rk = {i: k + 1 for k, i in enumerate([i for i in order if b["adm"][i]])}
    rows = [[alts[i], name[alts[i]], b["adm"][i], legal.alpha[i], b["models"]["M2"].uc[i], V[i], rk.get(i)] for i in order]
    r = table(ws, r, ["Kod", "Düzen", "Kabul edildi", "α_i (Eş. 7)", "û_ci, M2 (Eş. 15)", "V_i (Eş. 22)", "Sıra"], rows,
              widths=[34, 34, 12, 12, 14, 12, 8], highlight=lambda k: rows[k][6] == 1)
    d = b["diagnostics"]
    rows = [[mname, d[mname]["LPS"], d[mname]["C_beta"], d[mname]["total_burden"], d[mname]["weighted_burden"]] for mname in ("M0", "M1", "M2")]
    r = title(ws, r, "Uzlaşı modelleri ve göstergeler (Eş. 23–25)",
              f"γ = {b['gamma']:.4f}; L = {int(b['L'].sum())} karar verici; koruma maliyeti CoP = {d.get('CoP', 0):.4f}")
    r = table(ws, r, ["Model", "LPS", "C_β", "Toplam yük Σβ", "Güç ağırlıklı yük Σpβ"], rows)
    vt = res["voice"]
    rows = []
    for mname in ("M2", "M1"):
        v = vt[mname]
        gt = f"> {P['voice_s_max']}"
        rows.append([mname, alts[v["i_L"]] if v.get("i_L") is not None else v.get("note"),
                     v.get("s_star") if v.get("s_star") is not None else gt,
                     v.get("s_stable") if v.get("s_stable") is not None else gt, v.get("share")])
    r = title(ws, r, "Ses eşiği (Eş. 26–28)", f"L'nin şu anki toplam ağırlığı: {b['omega'][b['L']].sum():.4f}")
    r = table(ws, r, ["Model", "L'nin tercih ettiği düzen i_L", "s*", "Kararlı eşik s^st", "Ses payı φ_L"], rows)
    if "dirichlet" in res:
        f = res["dirichlet"]["f"]
        r = title(ws, r, f"Ağırlık belirsizliği: birinci olma sıklığı f_i (Eş. 34), Y = {res['dirichlet']['Y']}")
        r = table(ws, r, ["Kod", "Düzen", "f_i"], [[a, name[a], f[i]] for i, a in enumerate(alts)])
    if "benchmarks" in res:
        bm = res["benchmarks"]["methods"]
        r = title(ws, r, "Karşılaştırma yöntemleriyle uyum (Adım 22)", f"Referans: û_ci (M2) sıralaması, en iyi {res['benchmarks']['ref_top']}")
        r = table(ws, r, ["Yöntem", "En iyi düzen", "Aynı mı", "Spearman ρ_S"], [[k, v["top"], v["same_top"], v["spearman"]] for k, v in bm.items()])

    # -------------------------------------------------------------- Aşama I
    if stage1_rows:
        ws = wb.create_sheet("Aşama I CVR")
        r = title(ws, 1, "İçerik geçerliği (Eş. 1–3)", f"Uzman sayısı: {len(experts or [])}")
        r = table(ws, r, ["Öğe", "N", "N^E", "CVR", "N^E_crit", "CVR_crit", "Korundu"],
                  [[x["item"], x["N"], x["NE"], x["CVR"], x["NE_crit"], x["CVR_crit"], x["retained"]] for x in stage1_rows],
                  widths=[10, 6, 6, 10, 10, 10, 10])
        if experts:
            rows = []
            for e in experts:
                for q, cm in e.comments.items():
                    if cm or e.clarity.get(q) == "Hayır":
                        rows.append([e.code, q, e.clarity.get(q), cm])
                for s in e.suggestions:
                    rows.append([e.code, "Öneri: " + str(s.get("item")), s.get("type"), f"{s.get('definition')} | {s.get('why')}"])
            if rows:
                r = title(ws, r, "Uzman yorumları ve önerileri (Adım 3'teki gözden geçirme için)")
                table(ws, r, ["Uzman", "Öğe", "Tanım açık mı", "Yorum"], rows, widths=[8, 24, 14, 90])

    # ------------------------------------------------------------- Aşama II
    ws = wb.create_sheet("Aşama II hukuk")
    nos = case.no_mask.sum(0)
    r = title(ws, 1, "Uygulanabilir gereklilikler ℛ* (Eş. 3)")
    r = table(ws, r, ["Gereklilik", "'Uygulanmaz' diyen hukukçu", "H/2", "ℛ*'da"],
              [[q, int(nos[j]), len(case.lawyers) / 2, bool(legal.rmask[j])] for j, q in enumerate(reqs)], widths=[14, 14, 8, 10])
    r = title(ws, r, "Ortalama T̄, Ī, F̄ (Eş. 4)")
    rows = [[a, q, legal.Tbar[i, j], legal.Ibar[i, j], legal.Fbar[i, j]] for i, a in enumerate(alts) for j, q in enumerate(reqs)]
    r = table(ws, r, ["Düzen", "Gereklilik", "T̄", "Ī", "F̄"], rows)
    r = title(ws, r, f"Birleşik değerler ve kabul (Eş. 5–7), τ_F = {P['tau_F']}, θ = {P['theta']}")
    table(ws, r, ["Düzen", "T_i", "I_i", "F_i", "Kabul edildi", "α_i", "χ_i (Eş. 31)"],
          [[a, legal.T[i], legal.I[i], legal.F[i], bool(legal.admissible[i]), legal.alpha[i], legal.chi[i]] for i, a in enumerate(alts)])

    # ------------------------------------------------------------ Aşama III
    ws = wb.create_sheet("Aşama III ağırlık")
    r = title(ws, 1, "Küresel ağırlıklar w_kj (Eş. 10) ve güç")
    rows = [[k, case.groups[i], case.levels[i], b["p"][i]] + list(res["W"][i]) for i, k in enumerate(case.dms)]
    r = table(ws, r, ["Kod", "Grup", "Kademe", "p_k"] + crits, rows, widths=[8, 26, 20, 8] + [9] * len(crits))
    r = title(ws, r, "BWM tutarlılığı (Eş. 9; eşik: Liang ve ark., 2020)")
    rows = []
    for i, k in enumerate(case.dms):
        for blk, br in res["detail"][i]["bwm"].items():
            rows.append([k, "Boyutlar" if blk == "dim" else blk, br.a_BW, br.xi, br.CR, br.threshold, br.inconsistent])
    r = table(ws, r, ["Kod", "Blok", "a_BW", "ξ", "CR^I", "Eşik", "Eşiği aşıyor"], rows)
    r = title(ws, r, "Bireysel faydalar u_ki (Eş. 13)")
    table(ws, r, ["Kod"] + alts, [[k] + list(b["U"][i]) for i, k in enumerate(case.dms)])

    # ------------------------------------------------------------- Aşama IV
    ws = wb.create_sheet("Aşama IV uzlaşı")
    r = title(ws, 1, "Ortak faydalar û_ci (Eş. 15)")
    r = table(ws, r, ["Model"] + alts, [[mn] + list(b["models"][mn].uc) for mn in ("M0", "M1", "M2")] +
              [["Uyarlamasız u_ci"] + list(b["omega"] @ b["U"])])
    r = title(ws, r, "Yükler β_k (Eş. 17) ve uzlaşı düzeyleri")
    rows = [[k, b["L"][i], b["omega"][i], b["CL0"][i]] + [b["models"][mn].beta[i] for mn in ("M0", "M1", "M2")] +
            [b["models"]["M2"].CL[i]] for i, k in enumerate(case.dms)]
    table(ws, r, ["Kod", "L'de", "ω_k", "CL⁰_k", "β M0", "β M1", "β M2", "CL_k M2"], rows)

    # -------------------------------------------------------------- ses eşiği
    ws = wb.create_sheet("Ses eşiği")
    r = title(ws, 1, "Izgaradaki her s için birinci düzen (Eş. 27–28)")
    tops2, tops1 = res["voice"]["M2"].get("tops", []), res["voice"]["M1"].get("tops", [])
    table(ws, r, ["s", "Birinci (M2)", "Birinci (M1)"],
          [[float(s), alts[t2] if t2 is not None else None, alts[t1] if t1 is not None else None]
           for s, t2, t1 in zip(res["grid"], tops2 or [None] * len(res["grid"]), tops1 or [None] * len(res["grid"]))], fmt="0.00")

    # ------------------------------------------------------------- Aşama V
    ws = wb.create_sheet("Aşama V testler")
    r = 1
    if "benchmarks" in res:
        bm = res["benchmarks"]
        adm_alts = [a for a, ok in zip(alts, b["adm"]) if ok]
        r = title(ws, r, "Karşılaştırma yöntemlerinin sıraları (Adım 21; Ek B)")
        r = table(ws, r, ["Düzen", "û_ci (M2) sırası"] + list(bm["methods"]),
                  [[a, bm["ref_rank"][i]] + [bm["methods"][mn]["rank"][i] for mn in bm["methods"]] for i, a in enumerate(adm_alts)], fmt="0.0")
    r = title(ws, r, "Hukuki gerekliliklerin farklı işlenmesi (Adım 23)")
    lt = res["legal_treatments"]
    r = table(ws, r, ["Yaklaşım", "Birinci", "Taramadan farklı", "Elenen düzen birinci"],
              [[k, v["top"], v["differs"], v["excluded_first"]] for k, v in lt.items()])
    r = title(ws, r, "Tek tek değişiklik (Adım 25)", "Spearman, taban sıralamayla her iki sırada kabul edilen düzenler üzerinden.")
    table(ws, r, ["Test", "Ayar", "Birinci", "Birinci değişti", "Spearman ρ_S", "Kabul edilenler"],
          [[x["test"], x["setting"], x["top"], x["top_changed"], x["spearman"], x["admissible"]] for x in res["oat"]],
          widths=[22, 22, 10, 14, 12, 40])

    # ---------------------------------------------------------------- uyarılar
    ws = wb.create_sheet("Uyarılar")
    rows = [["Form", x] for x in case.issues] + [["Analizden çıkarılan", f"{x['code']}: {x['reason']}"] for x in case.excluded_dms]
    rows += [["Aşama II", x] for x in legal.notes]
    rows += [["Aşama IV", x] for x in res.get("notes", [])]
    for i, k in enumerate(case.dms):
        for blk, br in res["detail"][i]["bwm"].items():
            rows += [["BWM", f"{k} {blk}: {n}"] for n in br.notes]
    table(ws, 1, ["Kaynak", "Açıklama"], rows or [["—", "Uyarı yok"]], widths=[20, 110])
    for w in wb.worksheets:
        w.sheet_view.showGridLines = False
    wb.save(path)


def summary_json(path, case, cfg, res, stage1_rows=None):
    b = res["base"]
    alts = np.array(case.alts)
    out = dict(
        K=len(case.dms), H=len(case.lawyers), excluded_dms=case.excluded_dms,
        admissible=list(alts[b["adm"]]), alpha=dict(zip(case.alts, map(float, b["legal"].alpha))),
        V=dict(zip(case.alts, [None if np.isnan(v) else float(v) for v in b["V"]])),
        top=alts[b["top"]] if b["top"] is not None else None, gamma=b["gamma"],
        diagnostics=b["diagnostics"],
        voice={k: dict(i_L=(alts[v["i_L"]] if v.get("i_L") is not None else None), s_star=v.get("s_star"),
                       s_stable=v.get("s_stable"), share=v.get("share")) for k, v in res["voice"].items()},
        dirichlet=dict(zip(case.alts, map(float, res["dirichlet"]["f"]))) if "dirichlet" in res else None,
        benchmarks={k: dict(top=v["top"], same_top=v["same_top"], spearman=v["spearman"]) for k, v in res.get("benchmarks", {}).get("methods", {}).items()},
        legal_treatments={k: dict(top=v["top"], differs=bool(v["differs"]), excluded_first=bool(v["excluded_first"])) for k, v in res["legal_treatments"].items()},
        oat=[{k: (bool(v) if isinstance(v, (bool, np.bool_)) else v) for k, v in x.items()} for x in res["oat"]],
        stage1=stage1_rows,
    )
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
