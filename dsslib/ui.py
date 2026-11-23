"""Arayüz için tek giriş noktası: formları çalıştırır ve sayfanın çizdiği JSON yükünü üretir.

Tarayıcıda (Pyodide) ve yerelde aynı kod çalışır.
"""
from __future__ import annotations

import copy
import json
import os
import time

import numpy as np

from . import engine as E
from .forms import read_folder
from .pipeline import build_case, load_config, run_all
from .report import summary_json, write_report


def _f(x):
    if x is None:
        return None
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    x = float(x)
    return None if np.isnan(x) else round(x, 6)


def _l(a):
    return [_f(v) for v in np.asarray(a).ravel()] if np.asarray(a).ndim == 1 else [_l(r) for r in np.asarray(a)]


def apply_params(cfg, params):
    cfg = copy.deepcopy(cfg)
    P = cfg["parameters"]
    for k in ("tau_F", "theta", "gamma_percentile", "delta", "dirichlet_draws", "dirichlet_kappa"):
        if params.get(k) is not None:
            P[k] = params[k]
    mp = params.get("power_mapping")
    if mp and mp != "base":
        P["power_mappings"] = dict(P["power_mappings"])
        P["power_mappings"]["base"] = P["power_mappings"][mp]
    return cfg


def stage1_rows(experts, cfg):
    items = [a["code"] for a in cfg["alternatives"]] + [c["code"] for c in cfg["criteria"]]
    ratings = {q: [e.ratings.get(q) for e in experts if e.ratings.get(q)] for q in items}
    return E.stage1(ratings, essential=cfg["cvr_scale"][0], alpha=cfg["parameters"]["cvr_alpha"])


def payload(case, cfg, res, s1, experts, source, seconds):
    alts = case.alts
    b = res["base"]
    lg = b["legal"]
    P = cfg["parameters"]
    out = dict(
        source=source, seconds=round(seconds, 1),
        params=dict(tau_F=P["tau_F"], theta=P["theta"], gamma_percentile=P["gamma_percentile"], delta=P["delta"],
                    power=dict(zip([lv["name"] for lv in cfg["levels"]], P["power_mappings"]["base"])),
                    voice_s_max=P["voice_s_max"], voice_step=P["voice_step"], kappa=P["dirichlet_kappa"]),
        alts=[dict(code=a["code"], name=a["name"], definition=a["definition"]) for a in cfg["alternatives"]],
        crits=[dict(code=c["code"], name=c["name"], type=c["type"], dim=c["dimension"]) for c in cfg["criteria"]],
        dims=[dict(code=d["code"], name=d["name"]) for d in cfg["dimensions"]],
        reqs=[dict(code=q["code"], source=q["source"]) for q in cfg["requirements"]],
        counts=dict(experts=len(experts), lawyers=len(case.lawyers), dms=len(case.dms), excluded=case.excluded_dms),
        issues=case.issues + [n for n in lg.notes] + res.get("notes", []),
        stage1=s1,
        legal=dict(rmask=_l(lg.rmask), no=_l(case.no_mask.sum(0)), H=len(case.lawyers),
                   Tbar=_l(lg.Tbar), Ibar=_l(lg.Ibar), Fbar=_l(lg.Fbar), T=_l(lg.T), I=_l(lg.I), F=_l(lg.F),
                   adm=_l(lg.admissible), alpha=_l(lg.alpha), chi=_l(lg.chi)),
        dms=[dict(code=k, group=case.groups[i], level=case.levels[i], p=_f(b["p"][i]), L=_f(b["L"][i]),
                  omega=_f(b["omega"][i]), w=_l(res["W"][i]), u=_l(b["U"][i]), CL0=_f(b["CL0"][i]),
                  inconsistent=bool(res["detail"][i]["inconsistent"]),
                  blocks=[dict(block=blk, a_BW=_f(r.a_BW), xi=_f(r.xi), CR=_f(r.CR), thr=_f(r.threshold), flag=bool(r.inconsistent))
                          for blk, r in res["detail"][i]["bwm"].items()])
             for i, k in enumerate(case.dms)],
        gamma=_f(b["gamma"]),
        models={m: dict(uc=_l(r.uc), beta=_l(r.beta), CL=_l(r.CL), objective=_f(r.objective)) for m, r in b["models"].items()},
        Z0=_f(b["models"]["M0"].Z0), beta_L0=_f(b["models"]["M0"].beta_L0),
        diagnostics={k: ({kk: _f(vv) for kk, vv in v.items()} if isinstance(v, dict) else _f(v)) for k, v in b["diagnostics"].items()},
        V=_l(b["V"]), top=(alts[b["top"]] if b["top"] is not None else None), tie=bool(b["tie"]),
        voice={m: dict(i_L=(alts[v["i_L"]] if v.get("i_L") is not None else None), s_star=_f(v.get("s_star")),
                       s_stable=_f(v.get("s_stable")), share=_f(v.get("share")),
                       tops=[alts[t] for t in v.get("tops", [])], note=v.get("note")) for m, v in res["voice"].items()},
        grid=_l(res["grid"]),
        L_share=_f(b["omega"][b["L"]].sum()),
        legal_treatments={k: dict(top=v["top"], differs=bool(v["differs"]), excluded_first=bool(v["excluded_first"]))
                          for k, v in res["legal_treatments"].items()},
        oat=[{k: (_f(v) if isinstance(v, (float, np.floating, bool, np.bool_)) else v) for k, v in x.items()} for x in res["oat"]],
        dirichlet=(dict(Y=res["dirichlet"]["Y"], f=_l(res["dirichlet"]["f"])) if "dirichlet" in res else None),
    )
    if "benchmarks" in res:
        bm = res["benchmarks"]
        adm_codes = [a for a, ok in zip(alts, lg.admissible) if ok]
        out["benchmarks"] = dict(alts=adm_codes, ref_rank=_l(bm["ref_rank"]), ref_top=str(bm["ref_top"]),
                                 methods={k: dict(rank=_l(v["rank"]), top=str(v["top"]), same_top=bool(v["same_top"]),
                                                  spearman=_f(v["spearman"])) for k, v in bm["methods"].items()})
    return out


def run(forms_dir, params=None, draws=None, dirichlet=True, out_dir=None, source="uploaded", workers=1, config=None):
    """Formları çalıştırır; JSON yükünü döndürür. out_dir verilirse Excel raporu ve JSON özeti yazılır."""
    t0 = time.time()
    cfg = apply_params(config or load_config(), params or {})
    forms = read_folder(forms_dir)
    experts = forms["experts"]
    s1 = stage1_rows(experts, cfg) if experts else None
    if not (forms["lawyers"] and forms["dms"]):
        return dict(source=source, stage1_only=True, stage1=s1, counts=dict(experts=len(experts), lawyers=len(forms["lawyers"]),
                    dms=len(forms["dms"])), alts=cfg["alternatives"], crits=cfg["criteria"],
                    issues=[i for e in experts for i in e.issues])
    case = build_case(forms, cfg)
    if len(case.dms) < 2:
        return dict(source=source, error="Analize girebilecek en az iki karar verici formu gerekli.", issues=case.issues,
                    counts=dict(experts=len(experts), lawyers=len(case.lawyers), dms=len(case.dms), excluded=case.excluded_dms))
    res = run_all(case, cfg, draws=draws, progress=1, skip_dirichlet=not dirichlet, workers=workers)
    out = payload(case, cfg, res, s1, experts, source, time.time() - t0)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        write_report(os.path.join(out_dir, "DSS_Rapor.xlsx"), case, cfg, res, s1, experts)
        summary_json(os.path.join(out_dir, "DSS_Ozet.json"), case, cfg, res, s1)
    return out


def run_json(forms_dir, params_json="{}", draws=None, dirichlet=True, out_dir=None, source="uploaded"):
    """Pyodide köprüsü: JSON metni alır, JSON metni döndürür."""
    try:
        return json.dumps(run(forms_dir, json.loads(params_json), draws, dirichlet, out_dir, source), ensure_ascii=False)
    except Exception as exc:  # hata sayfada gösterilir
        import traceback
        return json.dumps(dict(error=f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()), ensure_ascii=False)
