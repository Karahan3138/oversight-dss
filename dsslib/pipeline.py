"""Uçtan uca analiz: formlar -> Aşama I–V.

`build_case` formlardan dizileri kurar, `analyse` Aşama II–IV'ü bir ayar kümesiyle çalıştırır,
`run_all` taban çözümü, ses eşiğini ve Aşama V testlerini üretir.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import rankdata

from . import engine as E
from .benchmarks import all_methods

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(path=None):
    return json.load(open(path or os.path.join(HERE, "config.json"), encoding="utf-8"))


# ===================================================================== veriler
@dataclass
class Case:
    alts: list
    crits: list
    cost: np.ndarray
    dims: list
    dim_of: np.ndarray
    reqs: list
    lawyers: list
    app: np.ndarray          # (H, R) yanıtlar
    no_mask: np.ndarray      # (H, R)
    T: np.ndarray            # (H, m, R)
    I: np.ndarray
    F: np.ndarray
    dms: list                # kodlar
    groups: list
    levels: list
    blocks: list             # her karar verici için blok sözlüğü
    g: np.ndarray            # (K, m, n)
    excluded_dms: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def build_case(forms: dict, cfg: dict) -> Case:
    alts = [a["code"] for a in cfg["alternatives"]]
    crits = [c["code"] for c in cfg["criteria"]]
    cost = np.array([c["type"] == "cost" for c in cfg["criteria"]])
    dims = [d["code"] for d in cfg["dimensions"]]
    dim_of = np.array([dims.index(c["dimension"]) for c in cfg["criteria"]])
    reqs = [q["code"] for q in cfg["requirements"]]
    issues = []
    # hukukçular
    Ls = forms["lawyers"]
    H, m, R = len(Ls), len(alts), len(reqs)
    app = np.array([[f.applicability.get(q) for q in reqs] for f in Ls], dtype=object).reshape(H, R)
    no_mask = np.vectorize(lambda v: v in cfg["applicability_no"])(app) if H else np.zeros((0, R), bool)
    T = np.full((H, m, R), np.nan); I = T.copy(); F = T.copy()
    for h, f in enumerate(Ls):
        issues += f.issues
        for i, a in enumerate(alts):
            for r, q in enumerate(reqs):
                T[h, i, r] = f.T.get((a, q), np.nan); I[h, i, r] = f.I.get((a, q), np.nan); F[h, i, r] = f.F.get((a, q), np.nan)
    # karar vericiler: kullanılamayan formlar analizden çıkarılır
    dms, groups, levels, blocks, G, excluded = [], [], [], [], [], []
    level_names = [lv["name"] for lv in cfg["levels"]]
    for f in forms["dms"]:
        issues += f.issues
        bad = [k for k, b in f.blocks.items() if not b["ok"]]
        miss = [k for k, v in f.ratings.items() if v is None]
        need = ["dim"] + [d for d in dims if len(cfg["dimensions"][dims.index(d)]["criteria"]) > 1]
        absent = [k for k in need if k not in f.blocks]
        if bad or miss or absent or f.level not in level_names:
            excluded.append(dict(code=f.code, reason=f"blok sorunu {bad + absent}" if (bad or absent) else
                                 ("eksik puan" if miss else "kademe geçersiz")))
            continue
        dms.append(f.code); groups.append(f.group); levels.append(f.level); blocks.append(f.blocks)
        G.append([[f.ratings[(a, c)] for c in crits] for a in alts])
    g = np.array(G, dtype=int).reshape(len(dms), m, len(crits))
    return Case(alts, crits, cost, dims, dim_of, reqs, [f.code for f in Ls], app, no_mask, T, I, F,
                dms, groups, levels, blocks, g, excluded, issues)


# ============================================================== Aşama III ağırlık
def dm_weights(case: Case, cfg: dict):
    """Her karar verici için iki düzeyli BWM (Eş. 8–10). Döndürür: w (K, n), ayrıntılar."""
    table = cfg["liang_thresholds"]
    W, detail = [], []
    for k, blks in enumerate(case.blocks):
        info = {}
        b = blks["dim"]
        order = [case.dims.index(e) for e in b["elems"]]
        res = E.bwm(b["elems"].index(b["best"]), b["elems"].index(b["worst"]), b["a_B"], b["a_W"], table)
        w_dim = np.zeros(len(case.dims)); w_dim[order] = res.weights
        info["dim"] = res
        w_loc = {}
        for d_i, d in enumerate(case.dims):
            members = [c for c, di in zip(case.crits, case.dim_of) if di == d_i]
            if len(members) == 1:
                w_loc[d_i] = np.ones(1); continue
            bb = blks[d]
            r = E.bwm(bb["elems"].index(bb["best"]), bb["elems"].index(bb["worst"]), bb["a_B"], bb["a_W"], table)
            loc = np.zeros(len(members))
            for e, wv in zip(bb["elems"], r.weights):
                loc[members.index(e)] = wv
            w_loc[d_i] = loc
            info[d] = r
        W.append(E.global_weights(w_dim, w_loc, case.dim_of))
        detail.append(dict(w_dim=w_dim, w_loc=w_loc, bwm=info,
                           inconsistent=any(r.inconsistent for r in info.values())))
    return np.array(W), detail


# ====================================================================== analiz
def power(case: Case, cfg: dict, mapping="base"):
    names = [lv["name"] for lv in cfg["levels"]]
    vals = cfg["parameters"]["power_mappings"][mapping]
    return np.array([vals[names.index(lv)] for lv in case.levels], float)


def analyse(case: Case, cfg: dict, W: np.ndarray, X: np.ndarray, *, mapping="base", tau=None, theta=None,
            pi=None, delta=None, keep=None, all_requirements=False, L_full=None, full=False):
    """Aşama II–IV'ü verilen ayarlarla çalıştırır. keep: dahil edilecek karar vericiler (bool)."""
    P = cfg["parameters"]
    tau = P["tau_F"] if tau is None else tau
    theta = P["theta"] if theta is None else theta
    pi = P["gamma_percentile"] if pi is None else pi
    delta = P["delta"] if delta is None else delta
    keep = np.ones(len(case.dms), bool) if keep is None else keep
    # Aşama II
    rmask = np.ones(len(case.reqs), bool) if all_requirements else E.applicable_requirements(case.app, case.no_mask)
    legal = E.legal_screen(case.T, case.I, case.F, rmask, tau, theta)
    # Aşama III
    Wk, Xk = W[keep], X[keep]
    U = E.utilities(Wk, Xk)
    # Aşama IV
    p_all = power(case, cfg, mapping)
    p = p_all[keep]
    if L_full is None:
        L_full = p_all == p_all.min()
    L = L_full[keep]
    omega = E.omega_from_power(p)
    gamma = E.gamma_threshold(U, omega, pi)
    models = E.run_models(U, p, L, gamma, delta, omega=omega)
    V = E.group_scores(legal.alpha, models["M2"].uc, legal.admissible)
    top, tie = E.top_of(V)
    out = dict(V=V, adm=legal.admissible, top=top if legal.admissible.any() else None, tie=tie)
    if full:
        out.update(legal=legal, U=U, p=p, L=L, omega=omega, gamma=gamma, models=models,
                   diagnostics=E.diagnostics(models, p, L), CL0=E.consensus_levels(U, omega),
                   V_M1=E.group_scores(legal.alpha, models["M1"].uc, legal.admissible))
    return out


def ranks_desc(scores, mask):
    """Azalan sıra (1 = en iyi), eşitlere ortalama sıra; maske dışı NaN."""
    r = np.full(len(scores), np.nan)
    r[mask] = rankdata(-scores[mask], method="average")
    return r


def spearman(ra, rb):
    """Eş. 30: ortalama sıralar üzerinde Pearson korelasyonu (her iki sırada bulunanlar)."""
    m = ~np.isnan(ra) & ~np.isnan(rb)
    if m.sum() < 2:
        return float("nan")
    a = rankdata(ra[m]); b = rankdata(rb[m])
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


# ======================================================================= Aşama V
def benchmarks(case, cfg, base, X, W):
    """Adım 21–22."""
    adm = base["adm"]
    Xc = np.einsum("k,kij->ij", base["omega"], X)[adm]           # Eş. 29
    wc = base["omega"] @ W
    ref = base["models"]["M2"].uc[adm]
    ref_rank = rankdata(-ref, method="average")
    ref_top = int(np.argmax(ref))
    out = {}
    for name, (score, higher) in all_methods(Xc, wc, case.cost, cfg["parameters"]).items():
        rk = rankdata(-score if higher else score, method="average")
        a = np.corrcoef(rankdata(ref_rank), rankdata(rk))[0, 1] if len(rk) > 1 else float("nan")
        top = int(np.argmin(rk))
        out[name] = dict(score=score, rank=rk, top=np.array(case.alts)[adm][top],
                         same_top=bool(top == ref_top), spearman=float(a))
    return dict(Xc=Xc, wc=wc, ref=ref, ref_rank=ref_rank, ref_top=np.array(case.alts)[adm][ref_top], methods=out)


def legal_treatments(case, cfg, base):
    """Adım 23 (Eş. 31–32)."""
    legal, uc = base["legal"], base["models"]["M2"].uc
    n = len(case.crits)
    alts = np.array(case.alts)
    screen_top = alts[base["top"]] if base["top"] is not None else None
    res = {}
    t_none = int(np.argmax(uc))
    vcomp = n / (n + 1) * uc + 1 / (n + 1) * legal.chi              # Eş. 31
    t_comp = int(np.argmax(vcomp))
    gate = (legal.T >= cfg["parameters"]["binary_gate_T"] - E.TOL) & (legal.F < cfg["parameters"]["binary_gate_F"] - E.TOL)
    t_gate, _ = E.top_of(np.where(gate, uc, np.nan)) if gate.any() else (None, False)
    for name, t, sc in (("Tarama yok", t_none, uc), ("Telafi edici", t_comp, vcomp),
                        ("İkili kapı", t_gate, np.where(gate, uc, np.nan))):
        res[name] = dict(top=alts[t] if t is not None else None, scores=sc,
                         differs=(t is None or alts[t] != screen_top),
                         excluded_first=(t is not None and not legal.admissible[t]))
    res["İkili kapı"]["admitted"] = list(alts[gate])
    return res


def _dirichlet_chunk(args):
    """Bir parça çekiliş; tohum parça numarasından türetilir (işçi sayısından bağımsız sonuç)."""
    seed_seq, n_draws, kappa, floor, details, dim_of, X, p, L, omega, alpha, adm, pi, delta, m = args
    rng = np.random.default_rng(seed_seq)
    f0 = E.TIEBREAK_FAILURES
    lp = E.ConsensusLP(omega, m)
    counts = np.zeros(m)
    K, n = X.shape[0], X.shape[2]
    for _ in range(n_draws):
        Wy = np.zeros((K, n))
        for k, (w_dim, w_loc) in enumerate(details):
            wd = rng.dirichlet(kappa * np.maximum(w_dim, floor))
            wl = {d: (rng.dirichlet(kappa * np.maximum(v, floor)) if len(v) > 1 else v) for d, v in w_loc.items()}
            Wy[k] = E.global_weights(wd, wl, dim_of)
        U = E.utilities(Wy, X)
        gamma = E.gamma_threshold(U, omega, pi)                    # Eş. 16, her çekilişte
        mods = E.run_models(U, p, L, gamma, delta, omega=omega, lp=lp, which=("M0", "M2"), m0_solution=False)
        t, _ = E.top_of(E.group_scores(alpha, mods["M2"].uc, adm))
        counts[t] += 1
    return counts, E.TIEBREAK_FAILURES - f0


def dirichlet(case, cfg, base, X, detail, Y=None, seed=None, progress=None, workers=None, chunks=40):
    """Adım 24 (Eş. 33–34). γ her çekilişte Eş. 16 ile yeniden hesaplanır.

    Çekilişler sabit sayıda parçaya bölünür; her parçanın tohumu SeedSequence ile türetilir.
    Böylece sonuç, kullanılan işlemci sayısından bağımsızdır.
    """
    P = cfg["parameters"]
    Y = P["dirichlet_draws"] if Y is None else Y
    seeds = np.random.SeedSequence(P["seed"] if seed is None else seed).spawn(chunks)
    sizes = [Y // chunks + (1 if c < Y % chunks else 0) for c in range(chunks)]
    details = [(d["w_dim"], d["w_loc"]) for d in detail]
    legal = base["legal"]
    jobs = [(seeds[c], sizes[c], P["dirichlet_kappa"], P["dirichlet_floor"], details, case.dim_of, X,
             base["p"], base["L"], base["omega"], legal.alpha, legal.admissible, P["gamma_percentile"],
             P["delta"], len(case.alts)) for c in range(chunks) if sizes[c] > 0]
    if workers == 1:                                   # tarayıcı (Pyodide): çok işlem yok
        parts = []
        for c, j in enumerate(jobs, 1):
            parts.append(_dirichlet_chunk(j))
            if progress:
                print(f"PROGRESS dirichlet {c}/{len(jobs)}", flush=True)
    else:
        import multiprocessing as mp
        workers = workers or max(1, min(mp.cpu_count(), len(jobs)))
        with mp.get_context("fork").Pool(workers) as pool:
            parts = pool.map(_dirichlet_chunk, jobs)
    counts = np.sum([c for c, _ in parts], axis=0)
    return dict(Y=Y, f=counts / Y, tiebreak_failures=int(sum(f for _, f in parts)))


def one_at_a_time(case, cfg, base, W, X, detail):
    """Adım 25."""
    P = cfg["parameters"]
    alts = np.array(case.alts)
    L_full = base["L_full"]
    base_rank = ranks_desc(base["V"], base["adm"])
    rows = []

    def rec(kind, setting, r):
        rk = ranks_desc(r["V"], r["adm"])
        top = alts[r["top"]] if r["top"] is not None else None
        rows.append(dict(test=kind, setting=setting, top=top,
                         top_changed=(top != alts[base["top"]]), spearman=spearman(base_rank, rk),
                         admissible=", ".join(alts[r["adm"]])))

    for t in P["tau_grid"]:
        rec("τ_F", t, analyse(case, cfg, W, X, tau=t, L_full=L_full))
    for th in P["theta_grid"]:
        rec("θ", th, analyse(case, cfg, W, X, theta=th, L_full=L_full))
    for pi in P["pi_grid"]:
        rec("π (γ yüzdeliği)", pi, analyse(case, cfg, W, X, pi=pi, L_full=L_full))
    for d in P["delta_grid"]:
        rec("δ", d, analyse(case, cfg, W, X, delta=d, L_full=L_full))
    for mp in P["power_mappings"]:
        if mp != "base":
            rec("Güç eşlemesi", mp, analyse(case, cfg, W, X, mapping=mp, L_full=L_full))
    groups = np.array(case.groups)
    for gname in sorted(set(case.groups), key=str):
        keep = groups != gname
        if keep.sum() >= 2:
            rec("Grup çıkarma", gname, analyse(case, cfg, W, X, keep=keep, L_full=L_full))
    for k, code in enumerate(case.dms):
        keep = np.ones(len(case.dms), bool); keep[k] = False
        rec("Karar verici çıkarma", code, analyse(case, cfg, W, X, keep=keep, L_full=L_full))
    inc = np.array([d["inconsistent"] for d in detail])
    if inc.any() and (~inc).sum() >= 2:
        rec("Tutarsız BWM çıkarma", f"{inc.sum()} karar verici", analyse(case, cfg, W, X, keep=~inc, L_full=L_full))
    elif inc.any():
        rows.append(dict(test="Tutarsız BWM çıkarma", setting=f"{inc.sum()} karar verici", top=None, top_changed=None,
                         spearman=float("nan"), admissible="Hesaplanamadı: tutarlı karar verici sayısı 2'den az"))
    rec("Tüm gereklilikler", f"R = {len(case.reqs)}", analyse(case, cfg, W, X, all_requirements=True, L_full=L_full))
    return rows


def run_all(case, cfg, draws=None, progress=None, skip_dirichlet=False, workers=None):
    P = cfg["parameters"]
    f0 = E.TIEBREAK_FAILURES
    svn = np.array(cfg["rating_scale"]["svn"])
    W, detail = dm_weights(case, cfg)
    X = E.performance(case.g, case.cost, svn)                     # (K, m, n)
    p_all = power(case, cfg)
    L_full = p_all == p_all.min()
    base = analyse(case, cfg, W, X, L_full=L_full, full=True)
    base["L_full"] = L_full
    grid = np.round(np.arange(0, P["voice_s_max"] + 1e-9, P["voice_step"]), 10)
    voice = {mname: E.voice_threshold(base["U"], base["p"], base["L"], base["gamma"], P["delta"],
                                      base["legal"].alpha, base["adm"], grid, mname) for mname in ("M2", "M1")}
    out = dict(W=W, X=X, detail=detail, base=base, voice=voice, grid=grid)
    if base["adm"].sum() >= 2:
        out["benchmarks"] = benchmarks(case, cfg, base, X, W)
    out["legal_treatments"] = legal_treatments(case, cfg, base)
    if not skip_dirichlet:
        out["dirichlet"] = dirichlet(case, cfg, base, X, detail, Y=draws, progress=progress, workers=workers)
    out["oat"] = one_at_a_time(case, cfg, base, W, X, detail)
    tb = E.TIEBREAK_FAILURES - f0
    if workers != 1 and "dirichlet" in out:            # çok işlemde sayaç alt süreçlerde artar
        tb += out["dirichlet"]["tiebreak_failures"]
    out["tiebreak_failures"] = tb
    out["notes"] = ([f"Uzlaşı çözümünün tekliğini sağlayan ikinci aşama (Adım 17) {tb} çözümde çalışmadı; "
                     "bu çözümlerde doğrusal programın ilk en iyi çözümü kullanıldı."] if tb else [])
    return out
