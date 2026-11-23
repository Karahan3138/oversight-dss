"""DSS'yi doldurulmuş formlarla çalıştırır.

Kullanım:
    python run_case.py --forms <klasör> --out <klasör> [--draws 10000] [--no-dirichlet]

<klasör> içinde U*_Uzman_Formu.xlsx, H*_Hukukcu_Formu.xlsx ve K*_Karar_Verici_Formu.xlsx
dosyaları (alt klasörlerde de olabilir). Çıktı: DSS_Rapor.xlsx ve DSS_Ozet.json.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dsslib import engine as E  # noqa: E402
from dsslib.forms import read_folder  # noqa: E402
from dsslib.pipeline import build_case, load_config, run_all  # noqa: E402
from dsslib.report import summary_json, write_report  # noqa: E402


def stage1_from_experts(experts, cfg):
    items = [a["code"] for a in cfg["alternatives"]] + [c["code"] for c in cfg["criteria"]]
    ratings = {q: [e.ratings.get(q) for e in experts if e.ratings.get(q)] for q in items}
    return E.stage1(ratings, essential=cfg["cvr_scale"][0], alpha=cfg["parameters"]["cvr_alpha"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--forms", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--draws", type=int, default=None)
    ap.add_argument("--no-dirichlet", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    forms = read_folder(a.forms)
    print(f"Okunan formlar: {len(forms['experts'])} uzman, {len(forms['lawyers'])} hukukçu, {len(forms['dms'])} karar verici")
    s1 = stage1_from_experts(forms["experts"], cfg) if forms["experts"] else None
    res = None
    if forms["lawyers"] and forms["dms"]:
        case = build_case(forms, cfg)
        print(f"Analize giren karar verici: {len(case.dms)} (çıkarılan {len(case.excluded_dms)})")
        res = run_all(case, cfg, draws=a.draws, progress=1000, skip_dirichlet=a.no_dirichlet)
        write_report(os.path.join(a.out, "DSS_Rapor.xlsx"), case, cfg, res, s1, forms["experts"])
        summary_json(os.path.join(a.out, "DSS_Ozet.json"), case, cfg, res, s1)
        b = res["base"]
        print("Öneri:", case.alts[b["top"]] if b["top"] is not None else "kabul edilen düzen yok")
    elif s1:
        import json
        json.dump(s1, open(os.path.join(a.out, "Asama1_CVR.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("Yalnızca Aşama I çalıştı:", sum(x["retained"] for x in s1), "öğe korundu")
    print(f"Süre: {time.time() - t0:.1f} sn")
    return res


if __name__ == "__main__":
    main()
