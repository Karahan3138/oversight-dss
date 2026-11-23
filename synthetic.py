"""Bölüm 5: sentetik değerlendirme, DSS motoruyla (dsslib.engine).

Tasarım scripts/model_c.py ile aynıdır: 8 karar verici, 4 grup, güç (1, .7, .7, .8, .6, .2, .2, .2),
iki senaryo (çatışmalı ve yapısız öncelikler), her senaryoda 300 Monte Carlo çalıştırması.
Hesaplar motorun fonksiyonlarıyla yapılır: Eş. 5–7 (legal_screen), Eş. 14–25 (run_models, diagnostics),
Eş. 26–28 (voice_threshold), Adım 23 (hukuki yaklaşımlar). Tüm sayılar sentetiktir.

python synthetic.py  ->  test_data/synthetic_results.json
"""
import json
import multiprocessing as mpc
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dsslib import engine as E  # noqa: E402

ALT = ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
# fayda yönlü performans (maliyet ölçütleri ters çevrilmiş); sentetik
P = np.array([
    [.20, .10, .60, .15, .05, .40, .20, .95, .95, .80],
    [.45, .25, .55, .40, .30, .25, .30, .75, .75, .70],
    [.50, .60, .55, .35, .25, .35, .40, .65, .65, .65],
    [.55, .70, .65, .65, .55, .50, .45, .55, .55, .65],
    [.65, .75, .70, .80, .85, .60, .65, .35, .40, .50],
    [.80, .75, .70, .75, .80, .65, .65, .20, .25, .35],
    [.60, .70, .65, .70, .60, .85, .70, .40, .55, .45]])
m, n = P.shape
DIMS = [[0, 1, 2, 3], [4, 5, 6], [7, 8, 9]]
GROUP = ["M", "M", "M", "LC", "IT", "E", "E", "E"]          # yönetim, hukuk/uyum, BT/veri, çalışanlar
p = np.array([1.0, .7, .7, .8, .6, .2, .2, .2])
L = p == p.min()
K = len(p)
PRIOR = {
    "M": ([.25, .25, .50], [[.25, .25, .25, .25], [.30, .40, .30], [.45, .40, .15]]),
    "LC": ([.35, .45, .20], [[.20, .30, .20, .30], [.40, .35, .25], [.35, .30, .35]]),
    "IT": ([.25, .45, .30], [[.20, .20, .35, .25], [.25, .45, .30], [.35, .35, .30]]),
    "E": ([.55, .30, .15], [[.30, .30, .15, .25], [.50, .20, .30], [.20, .20, .60]])}
FLAT = {g: ([1 / 3] * 3, [[.25] * 4, [1 / 3] * 3, [1 / 3] * 3]) for g in PRIOR}
# sentetik hukuki değerlendirmeler (T, I, F), düzen × gereklilik
LEG = [
    [(.10, .20, .85), (.30, .30, .60), (.60, .20, .20), (.05, .10, .90), (.10, .20, .80)],
    [(.60, .40, .20), (.70, .20, .10), (.60, .30, .20), (.40, .55, .30), (.50, .40, .20)],
    [(.60, .30, .20), (.70, .20, .10), (.60, .30, .20), (.50, .50, .25), (.55, .40, .20)],
    [(.75, .20, .10), (.75, .20, .10), (.65, .25, .15), (.75, .25, .10), (.80, .20, .10)],
    [(.85, .10, .05), (.80, .15, .05), (.70, .20, .10), (.85, .15, .05), (.85, .10, .05)],
    [(.85, .10, .05), (.85, .10, .05), (.70, .20, .10), (.85, .15, .05), (.85, .10, .05)],
    [(.80, .15, .10), (.85, .10, .05), (.70, .20, .10), (.75, .25, .10), (.80, .20, .10)]]
LEGA = np.array(LEG)                                          # (m, R, 3)
TAU, THETA, PI, DELTA = .60, .5, 75, 0.0
GRID = np.round(np.arange(0, .60 + 1e-9, .01), 2)
CONC, NOISE, RUNS = 60.0, .05, 300


def legal():
    T, I, F = (LEGA[None, :, :, c] for c in range(3))       # tek "hukukçu" = ortalama değerlendirme
    return E.legal_screen(T, I, F, np.ones(LEGA.shape[1], bool), TAU, THETA)


def utilities(rng, prior):
    U = np.zeros((K, m))
    for k in range(K):
        dimp, within = prior[GROUP[k]]
        wd = rng.dirichlet(CONC * np.array(dimp))
        w = np.zeros(n)
        for d, idx in enumerate(DIMS):
            w[idx] = wd[d] * rng.dirichlet(CONC * np.array(within[d]))
        X = np.clip(P + rng.normal(0, NOISE, P.shape), 0, 1)
        U[k] = X @ w
    return U


def one_run(U, lg, voice=True):
    omega = E.omega_from_power(p)
    gamma = E.gamma_threshold(U, omega, PI)
    mods = E.run_models(U, p, L, gamma, DELTA, omega=omega)
    d = E.diagnostics(mods, p, L)
    V2 = E.group_scores(lg.alpha, mods["M2"].uc, lg.admissible)
    V1 = E.group_scores(lg.alpha, mods["M1"].uc, lg.admissible)
    t2, _ = E.top_of(V2); t1, _ = E.top_of(V1)
    uc = mods["M2"].uc
    t_none = int(np.argmax(uc))
    t_comp = int(np.argmax(n / (n + 1) * uc + 1 / (n + 1) * lg.chi))
    gate = (lg.T >= .5) & (lg.F < .5)
    t_gate, _ = E.top_of(np.where(gate, uc, np.nan))
    out = dict(gamma=gamma,
               LPS={k: d[k]["LPS"] for k in ("M0", "M1", "M2")}, C={k: d[k]["C_beta"] for k in ("M0", "M1", "M2")},
               CoP=d["CoP"], binds=bool(mods["M1"].beta[L].sum() > mods["M0"].beta_L0 * (1 + 1e-6) + 1e-7),
               top_M1=t1, top_M2=t2, top_change=bool(t1 != t2),
               legal=dict(none=t_none, comp=t_comp, gate=t_gate, screen=t2,
                          none_excl=bool(not lg.admissible[t_none]), comp_excl=bool(not lg.admissible[t_comp])))
    if voice:
        out["voice"] = {mod: E.voice_threshold(U, p, L, gamma, DELTA, lg.alpha, lg.admissible, GRID, mod) for mod in ("M2", "M1")}
        for v in out["voice"].values():
            v.pop("tops", None)
    return out


def _mc(args):
    scen, seed, runs = args
    prior = PRIOR if scen == "conflict" else FLAT
    rng = np.random.default_rng(seed)
    lg = legal()
    return [one_run(utilities(rng, prior), lg) for _ in range(runs)]


def summarise(runs):
    q = lambda v: dict(mean=float(np.mean(v)), p10=float(np.quantile(v, .1)), p90=float(np.quantile(v, .9)))
    s = dict(
        LPS={k: q([r["LPS"][k] for r in runs]) for k in ("M0", "M1", "M2")},
        C={k: q([r["C"][k] for r in runs]) for k in ("M0", "M1", "M2")},
        CoP=q([r["CoP"] for r in runs]), binds=float(np.mean([r["binds"] for r in runs])),
        top_change=float(np.mean([r["top_change"] for r in runs])),
        legal=dict(differs_none=float(np.mean([r["legal"]["none"] != r["legal"]["screen"] for r in runs])),
                   differs_comp=float(np.mean([r["legal"]["comp"] != r["legal"]["screen"] for r in runs])),
                   differs_gate=float(np.mean([r["legal"]["gate"] != r["legal"]["screen"] for r in runs])),
                   excluded_first_none=float(np.mean([r["legal"]["none_excl"] for r in runs])),
                   excluded_first_comp=float(np.mean([r["legal"]["comp_excl"] for r in runs]))),
        tops_M2={a: float(np.mean([r["top_M2"] == i for r in runs])) for i, a in enumerate(ALT)},
        gamma=q([r["gamma"] for r in runs]))
    for mod in ("M2", "M1"):
        vs = [r["voice"][mod] for r in runs]
        win_any = [v["s_star"] is not None for v in vs]
        stable = [v["s_stable"] is not None for v in vs]
        s[f"voice_{mod}"] = dict(
            iL={a: float(np.mean([v["i_L"] == i for v in vs])) for i, a in enumerate(ALT)},
            any_win=float(np.mean(win_any)), stable_win=float(np.mean(stable)),
            s_star=q([v["s_star"] for v in vs if v["s_star"] is not None]) if any(win_any) else None,
            s_stable=q([v["s_stable"] for v in vs if v["s_stable"] is not None]) if any(stable) else None,
            share=q([v["share"] for v in vs]),
            isolated=float(np.mean([(v["s_star"] is not None) and (v["s_stable"] is None) for v in vs])),
            gap=q([v["s_stable"] - v["s_star"] for v in vs if v["s_stable"] is not None]) if any(stable) else None)
    return s


def demo():
    rng = np.random.default_rng(2026)
    U = utilities(rng, PRIOR)
    lg = legal()
    omega = E.omega_from_power(p)
    gamma = E.gamma_threshold(U, omega, PI)
    mods = E.run_models(U, p, L, gamma, DELTA, omega=omega)
    d = E.diagnostics(mods, p, L)
    V = E.group_scores(lg.alpha, mods["M2"].uc, lg.admissible)
    vt = {mod: E.voice_threshold(U, p, L, gamma, DELTA, lg.alpha, lg.admissible, GRID, mod) for mod in ("M2", "M1")}
    frontier = []
    for th in np.round(np.linspace(0, 1, 11), 1):
        lgt = E.legal_screen(*(LEGA[None, :, :, c] for c in range(3)), np.ones(5, bool), TAU, th)
        Vt = E.group_scores(lgt.alpha, mods["M2"].uc, lgt.admissible)
        frontier.append(dict(theta=float(th), ranking=[ALT[i] for i in np.argsort(-np.nan_to_num(Vt, nan=-1))]))
    return dict(
        U=U.round(4).tolist(), gamma=gamma, CL0=E.consensus_levels(U, omega).round(4).tolist(),
        individual_top=[ALT[int(np.argmax(U[k]))] for k in range(K)],
        legal=dict(T=lg.T.round(3).tolist(), I=lg.I.round(3).tolist(), F=lg.F.round(3).tolist(),
                   admissible=lg.admissible.tolist(), alpha=lg.alpha.round(4).tolist()),
        models={k: dict(beta=r.beta.round(4).tolist(), uc=r.uc.round(4).tolist(), objective=r.objective) for k, r in mods.items()},
        Z0=mods["M0"].Z0, beta_L0=mods["M0"].beta_L0, diagnostics=d,
        V=[None if np.isnan(v) else round(float(v), 4) for v in V], top=ALT[E.top_of(V)[0]],
        voice={k: dict(i_L=ALT[v["i_L"]], s_star=v["s_star"], s_stable=v["s_stable"], share=v["share"],
                       tops=[ALT[t] for t in v["tops"]]) for k, v in vt.items()},
        L_share=float(omega[L].sum()), frontier=frontier)


if __name__ == "__main__":
    t0 = time.time()
    res = dict(settings=dict(K=K, groups=GROUP, power=p.tolist(), runs=RUNS, conc=CONC, noise=NOISE, tau_F=TAU, theta=THETA,
                             gamma_percentile=PI, delta=DELTA, grid=[0, .60, .01]))
    res["demo"] = demo()
    print("demo", res["demo"]["top"], res["demo"]["voice"]["M2"]["s_star"], f"{time.time() - t0:.0f}s", flush=True)
    chunks = 10
    jobs = [(scen, s, RUNS // chunks) for scen, base in (("conflict", 7), ("unstructured", 7))
            for s in np.random.SeedSequence(base).spawn(chunks)]
    with mpc.get_context("fork").Pool(mpc.cpu_count()) as pool:
        parts = pool.map(_mc, jobs)
    for scen in ("conflict", "unstructured"):
        runs = [r for (sc, _, _), part in zip(jobs, parts) if sc == scen for r in part]
        res[scen] = summarise(runs)
        print(scen, json.dumps(res[scen], default=float)[:400], flush=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data", "synthetic_results.json")
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1, default=float)
    print("bitti", f"{time.time() - t0:.0f}s")
