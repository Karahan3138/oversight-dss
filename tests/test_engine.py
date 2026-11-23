"""Motorun doğrulama testleri.

Üç tür test var:
1. Yayımlanmış sayısal örnekler: CoCoSo (Yazdani ve ark., 2019, Tablo I ve VI),
   MABAC (Pamučar ve Ćirović, 2015, Tablo 7 ve 12), CR^I (Liang ve ark., 2020, Örnek 1).
2. Elle hesaplanan değerler: CVR kritik değerleri (Eş. 2), Tablo 3, Eş. 4–7, C_β.
3. Bağımsız ikinci uygulama: uzlaşı LP'si, model_c.py'deki yoğun matrisli kurulumla karşılaştırılır.
"""
import os
import sys
from math import comb

import numpy as np
import pytest
from scipy.optimize import linprog

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dsslib import engine as E  # noqa: E402
from dsslib import benchmarks as B  # noqa: E402
from dsslib.pipeline import load_config, spearman  # noqa: E402

CFG = load_config()
LIANG = CFG["liang_thresholds"]


# ---------------------------------------------------------------- Aşama I
@pytest.mark.parametrize("N,ne,cvr", [(5, 5, 1.0), (8, 7, 0.75), (10, 9, 0.8), (13, 10, 0.538), (15, 12, 0.6), (20, 15, 0.5)])
def test_cvr_critical(N, ne, cvr):
    got_ne, got_cvr = E.cvr_critical(N)
    assert got_ne == ne and got_cvr == pytest.approx(cvr, abs=1e-3)
    # tanım: N^E_crit'te kuyruk ≤ .05, bir altında > .05
    tail = lambda k: sum(comb(N, t) for t in range(k, N + 1)) / 2 ** N
    assert tail(ne) <= 0.05 < tail(ne - 1)


def test_cvr_no_critical_for_small_panel():
    assert E.cvr_critical(4) == (None, None)


# ---------------------------------------------------------------- Aşama II
def test_legal_screen_by_hand():
    # 2 hukukçu, 2 düzen, 2 gereklilik
    T = np.array([[[1, .5], [0, .25]], [[.5, .5], [0, .75]]], float)
    I = np.array([[[0, .5], [.25, 0]], [[.5, .5], [.25, 0]]], float)
    F = np.array([[[0, .25], [1, .5]], [[0, .25], [.5, .5]]], float)
    app = np.array([["Kesinlikle evet", "Muhtemelen hayır"], ["Belirsiz", "Kesinlikle hayır"]], dtype=object)
    no = np.isin(app, CFG["applicability_no"])
    rmask = E.applicable_requirements(app, no)
    assert rmask.tolist() == [True, False]                # R2: 2 'hayır' > H/2 = 1
    res = E.legal_screen(T, I, F, rmask, tau_F=.6, theta=.5)
    # yalnız R1: A1 T̄=.75 Ī=.25 F̄=0 ; A2 T̄=0 Ī=.25 F̄=.75
    assert res.T.tolist() == [.75, 0] and res.F.tolist() == [0, .75]
    assert res.admissible.tolist() == [True, False]
    assert res.alpha[0] == pytest.approx((.75 + .5 * .25) / 1.0) and res.alpha[1] == 0


def test_applicability_rule():
    app = np.array([["Muhtemelen hayır", "Belirsiz"], ["Kesinlikle hayır", "Muhtemelen hayır"], ["Muhtemelen evet", "Muhtemelen evet"]], dtype=object)
    no = np.isin(app, CFG["applicability_no"])
    # R1: 2 hayır > 3/2 -> dışarıda ; R2: 1 hayır ≤ 1.5 -> içeride
    assert E.applicable_requirements(app, no).tolist() == [False, True]


def test_neutrosophic_intersection_uses_max_indeterminacy():
    T = np.array([[[1, .5]]]); I = np.array([[[0, .75]]]); F = np.array([[[0, .25]]])
    res = E.legal_screen(T, I, F, np.array([True, True]), .6, .5)
    assert (res.T[0], res.I[0], res.F[0]) == (.5, .75, .25)   # Eş. 5: min T, max I, max F


# ---------------------------------------------------------------- Aşama III
def test_bwm_consistent_example():
    # w ∝ (8, 4, 2, 1): tam tutarlı yanıtlar -> ξ = 0, CR^I = 0
    aB, aW = np.array([1, 2, 4, 8.]), np.array([8, 4, 2, 1.])
    r = E.bwm(0, 3, aB, aW, LIANG)
    assert r.xi == pytest.approx(0, abs=1e-9)
    assert r.weights == pytest.approx(np.array([8, 4, 2, 1]) / 15, abs=1e-9)
    assert r.CR == 0 and not r.inconsistent


def test_liang_example_1():
    # Liang ve ark. (2020) Örnek 1: konfor ölçütü a_Bj = 4, a_jW = 4, a_BW = 8 -> 1/7
    aB, aW = np.array([1, 4, 8.]), np.array([8, 4, 1.])
    r = E.bwm(0, 2, aB, aW, LIANG)
    assert r.CR == pytest.approx(1 / 7, abs=1e-9)
    assert r.threshold == 0.1667 and not r.inconsistent


def test_liang_threshold_table():
    assert E.liang_threshold(4, 3, LIANG) == 0.1121
    assert E.liang_threshold(4, 9, LIANG) == 0.2683
    assert E.liang_threshold(3, 5, LIANG) == 0.1667
    assert E.liang_threshold(4, 2, LIANG) == 0.0
    assert E.liang_threshold(4, 1, LIANG) is None


def test_table3_performance():
    svn = np.array(CFG["rating_scale"]["svn"])
    x = E.performance(np.arange(11)[None, :], np.array([False] * 11), svn)[0]
    expected = [0, .1, .175, .275, .375, .5, .625, .725, .825, .9, 1]
    assert x == pytest.approx(expected, abs=1e-12)
    # simetri: x(10 − g) = 1 − x(g)  (Ek B'deki ARLON kuralının dayanağı)
    assert x[::-1] == pytest.approx(1 - x, abs=1e-12)
    xc = E.performance(np.arange(11)[None, :], np.array([True] * 11), svn)[0]
    assert xc == pytest.approx(expected[::-1], abs=1e-12)


def test_global_weights():
    w = E.global_weights(np.array([.5, .3, .2]), {0: np.array([.6, .4]), 1: np.array([1.]), 2: np.array([.5, .5])},
                         np.array([0, 0, 1, 2, 2]))
    assert w == pytest.approx([.3, .2, .3, .1, .1]) and w.sum() == pytest.approx(1)


# ----------------------------------------------------------------- Aşama IV
def dense_mcc(U, omega, cost, gamma, L=None, cap_L=None, minimize_L=False, total_cap=None):
    """model_c.py'deki kurulumun bağımsız kopyası (döngüyle yoğun matris)."""
    K, m = U.shape; N = K * m
    iu = lambda k, i: k * m + i; idd = lambda k, i: N + k * m + i; ie = lambda k, i: 2 * N + k * m + i
    A, b = [], []
    for k in range(K):
        for i in range(m):
            r = np.zeros(3 * N); r[iu(k, i)] = 1; r[idd(k, i)] = -1; A.append(r); b.append(U[k, i])
            r = np.zeros(3 * N); r[iu(k, i)] = -1; r[idd(k, i)] = -1; A.append(r); b.append(-U[k, i])
            r = np.zeros(3 * N); r[iu(k, i)] += 1; r[ie(k, i)] = -1
            for l in range(K):
                r[iu(l, i)] -= omega[l]
            A.append(r); b.append(0)
            r = np.zeros(3 * N); r[iu(k, i)] -= 1; r[ie(k, i)] = -1
            for l in range(K):
                r[iu(l, i)] += omega[l]
            A.append(r); b.append(0)
        r = np.zeros(3 * N)
        for i in range(m):
            r[ie(k, i)] = 1 / m
        A.append(r); b.append(1 - gamma)
    if cap_L is not None:
        r = np.zeros(3 * N)
        for k in np.where(L)[0]:
            for i in range(m):
                r[idd(k, i)] = 1
        A.append(r); b.append(cap_L)
    if total_cap is not None:
        r = np.zeros(3 * N); r[N:2 * N] = 1; A.append(r); b.append(total_cap)
    c = np.zeros(3 * N)
    for k in range(K):
        for i in range(m):
            c[idd(k, i)] = (1.0 if (minimize_L and L[k]) else 0.0) if minimize_L else cost[k]
    res = linprog(c, A_ub=np.array(A), b_ub=np.array(b), bounds=[(0, 1)] * N + [(0, None)] * (2 * N), method="highs")
    return res.fun


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_consensus_lp_matches_dense(seed):
    rng = np.random.default_rng(seed)
    K, m = 8, 6
    U = rng.uniform(.2, .8, (K, m))
    p = np.array([1, .8, .8, .6, .4, .2, .2, .2])
    L = p == p.min()
    om = p / p.sum()
    gamma = E.gamma_threshold(U, om, 75)
    res = E.run_models(U, p, L, gamma, 0.0)
    assert res["M1"].objective == pytest.approx(dense_mcc(U, om, p, gamma), rel=1e-6, abs=1e-9)
    Z0 = dense_mcc(U, om, np.ones(K), gamma)
    assert res["M0"].Z0 == pytest.approx(Z0, rel=1e-6, abs=1e-9)
    bL0 = dense_mcc(U, om, None, gamma, L=L, minimize_L=True, total_cap=Z0 * (1 + 1e-9) + 1e-10)
    assert res["M0"].beta_L0 == pytest.approx(bL0, rel=1e-6, abs=1e-9)
    assert res["M2"].objective == pytest.approx(dense_mcc(U, om, p, gamma, L=L, cap_L=bL0 * (1 + 1e-9) + 1e-10), rel=1e-6, abs=1e-9)
    # olurluluk ve sıralama ilişkileri
    for r in res.values():
        assert (r.CL >= gamma - 1e-7).all()
        assert ((r.Uhat >= -1e-9) & (r.Uhat <= 1 + 1e-9)).all()
    assert res["M2"].beta[L].sum() <= res["M0"].beta_L0 + 1e-7       # Eş. 20 tavanı
    assert res["M2"].objective >= res["M1"].objective - 1e-9          # CoP ≥ 0
    assert res["M0"].beta.sum() == pytest.approx(Z0, abs=1e-6)        # Eş. 19, ikinci aşama


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_tiebreak_gives_unique_solution(seed):
    """Eş. 21, ikinci aşama: düzenlerin sırası değişince çözüm de aynı biçimde değişmeli (tek çözüm)."""
    rng = np.random.default_rng(seed)
    U = rng.uniform(.2, .8, (8, 6))
    p = np.array([1, .8, .8, .6, .4, .2, .2, .2]); L = p == p.min(); om = p / p.sum()
    gamma = E.gamma_threshold(U, om, 75)
    perm = rng.permutation(U.shape[1])
    r1 = E.run_models(U, p, L, gamma, 0.0)
    r2 = E.run_models(U[:, perm], p, L, gamma, 0.0)
    assert E.TIEBREAK_FAILURES == 0
    for mname in ("M0", "M1", "M2"):
        assert r1[mname].uc[perm] == pytest.approx(r2[mname].uc, abs=1e-6)
        assert r1[mname].beta == pytest.approx(r2[mname].beta, abs=1e-6)
    # ikinci aşama birinci aşamanın optimumunu korur
    lp = E.ConsensusLP(om, U.shape[1])
    _, f_lp = lp.solve(U, gamma, cost=p, tiebreak=False)
    assert p @ r1["M1"].beta == pytest.approx(f_lp, rel=1e-6, abs=1e-8)


def test_concentration_index_by_hand():
    # β = (2, 1, 0), p = (.2, .6, 1): kesirli sıralar (1/6, 1/2, 5/6), μ = 1
    # cov = ((1)(−1/3) + 0 + (−1)(1/3))/3 = −2/9 -> C_β = −4/9
    r = E.ModelResult("x", None, None, np.array([2., 1., 0.]), None, 0)
    d = E.diagnostics({"M1": r}, np.array([.2, .6, 1.]), np.array([True, False, False]))
    assert d["M1"]["C_beta"] == pytest.approx(-4 / 9) and d["M1"]["LPS"] == pytest.approx(2 / 3)


def test_diagnostics_zero_when_no_adjustment():
    r = E.ModelResult("x", None, None, np.zeros(3), None, 0)
    d = E.diagnostics({"M1": r, "M2": r}, np.array([.2, .6, 1.]), np.array([True, False, False]))
    assert d["M1"]["LPS"] == 0 and d["M1"]["C_beta"] == 0 and d["CoP"] == 0


def test_voice_weights():
    p = np.array([1, .6, .2, .2]); L = p == .2
    w = E.voice_weights(p, L, .3)
    assert w[L] == pytest.approx([.15, .15]) and w[~L] == pytest.approx([.7 * 1 / 1.6, .7 * .6 / 1.6]) and w.sum() == pytest.approx(1)


def test_voice_stats():
    g = [0, .1, .2, .3, .4]
    assert E.voice_stats([1, 1, 2, 1, 1], 2, g) == dict(s_star=.2, s_stable=None, share=.2)
    assert E.voice_stats([1, 2, 1, 2, 2], 2, g) == dict(s_star=.1, s_stable=.3, share=.6)
    assert E.voice_stats([2, 2, 2, 2, 2], 2, g) == dict(s_star=0.0, s_stable=0.0, share=1.0)
    assert E.voice_stats([1, 1, 1, 1, 1], 2, g) == dict(s_star=None, s_stable=None, share=0.0)


# ---------------------------------------------------------------- Ek B
def test_cocoso_yazdani_example():
    X = np.array([[60, .4, 2540, 500, 990], [6.35, .15, 1016, 3000, 1041], [6.8, .1, 1727.2, 1500, 1676],
                  [10, .2, 1000, 2000, 965], [2.5, .1, 560, 500, 915], [4.5, .08, 1016, 350, 508], [3, .1, 1778, 1000, 920]])
    w = np.array([.036, .192, .326, .326, .12])
    cost = np.array([False, True, False, False, False])
    k = B.cocoso(X, w, .5, cost)
    assert k == pytest.approx([2.041, 2.788, 2.882, 2.416, 1.3, 1.443, 2.52], abs=0.006)
    assert list(np.argsort(-k) + 1) == [3, 2, 7, 4, 1, 6, 5]


def test_mabac_pamucar_example():
    X = np.array([[22600, 3800, 2, 5, 1.06, 3.00, 3.5, 2.8, 24.5, 6.5],
                  [19500, 4200, 3, 2, .95, 3.00, 3.4, 2.2, 24, 7.0],
                  [21700, 4000, 1, 3, 1.25, 3.20, 3.3, 2.5, 24.5, 7.3],
                  [20600, 3800, 2, 5, 1.05, 3.25, 3.2, 2.0, 22.5, 11.0],
                  [22500, 3800, 4, 3, 1.35, 3.20, 3.7, 2.1, 23, 6.3],
                  [23250, 4210, 3, 5, 1.45, 3.60, 3.5, 2.8, 23.5, 7.0],
                  [20300, 3850, 2, 5, .90, 3.25, 3.0, 2.6, 21.5, 6.0]])
    w = np.array([.146, .144, .119, .121, .115, .101, .088, .068, .050, .048])
    cost = np.zeros(10, bool); cost[[0, 4, 5]] = True
    S = B.mabac(X, w, cost)
    assert S == pytest.approx([.0826, .2183, -.0488, .0246, -.0704, .0465, .0464], abs=0.0015)
    assert list(np.argsort(-S) + 1) == [2, 1, 6, 7, 4, 3, 5]


def test_dominance_properties():
    X = np.array([[.2, .3, .1], [.5, .4, .6], [.9, .8, .7]])
    w = np.array([.5, .3, .2])
    assert B.topsis(X, w)[2] == pytest.approx(1) and B.topsis(X, w)[0] == pytest.approx(0)
    q, s, r = B.vikor(X, w)
    assert q[2] == pytest.approx(0) and s[2] == 0 and q[0] == pytest.approx(1)
    assert B.waspas(X, w)[2] == pytest.approx(1)
    assert np.argmax(B.cocoso(X, w)) == 2 and np.argmax(B.mabac(X, w)) == 2


def test_arlon_benefit_only_reduces():
    # yalnız fayda ölçütleri: iki normalleştirme aynı -> ζ etkisiz, ψ = 1 -> Q = S⁺ + 1
    X = np.array([[.2, .6], [.5, .4], [.9, .1]])
    w = np.array([.7, .3]); cost = np.array([False, False])
    q0, q1 = B.arlon(X, w, cost, zeta=0), B.arlon(X, w, cost, zeta=1)
    XA = 1 + 100 * X
    zz = np.log(XA) / np.log(XA).sum(0)
    assert q0 == pytest.approx(q1) and q0 == pytest.approx((w * zz).sum(1) + 1)


def test_arlon_cost_by_hand():
    # tek maliyet ölçütü, m = 2, ölçeksiz: x = (e, e²) -> ln = (1, 2), toplam 3
    X = np.array([[np.e], [np.e ** 2]])
    cost = np.array([True])
    z1 = np.array([(1 - 1 / 3) / 1, (1 - 2 / 3) / 1])
    z2 = 1 - np.array([1 / 3, 2 / 3])                 # log2 oranı ln oranıyla aynı
    z = .5 * np.sqrt(z1 * z2) + .5 * (z1 + z2) / 2
    q = B.arlon(X, np.array([1.0]), cost, zeta=.5, scale=False)
    assert q == pytest.approx(0 ** 0 + z ** 1)        # ψ = 0: (S⁺)^0 + (S⁻)^1


def test_flat_criterion_is_zero():
    X = np.array([[.5, .2], [.5, .8]])
    w = np.array([.5, .5])
    assert B.mabac(X, w)[0] < B.mabac(X, w)[1]
    assert B.topsis(X, w) == pytest.approx([0, 1])


# ------------------------------------------------------------ yardımcılar
def test_spearman():
    a = np.array([1, 2, 3, 4.]); assert spearman(a, a) == pytest.approx(1)
    assert spearman(a, a[::-1].copy()) == pytest.approx(-1)
    b = np.array([1, 2, np.nan, 3.]); assert spearman(a, b) == pytest.approx(1)


def test_end_to_end_on_test_data():
    from dsslib.forms import read_folder
    from dsslib.pipeline import build_case, run_all
    folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_data", "forms")
    if not os.path.isdir(folder):
        pytest.skip("deneme verisi yok")
    case = build_case(read_folder(folder), CFG)
    res = run_all(case, CFG, draws=40)
    b = res["base"]
    for mname, r in b["models"].items():
        assert (r.CL >= b["gamma"] - 1e-7).all(), mname
    assert np.nansum(b["V"]) > 0 and res["dirichlet"]["f"].sum() == pytest.approx(1)
    assert np.isnan(b["V"][~b["adm"]]).all()
