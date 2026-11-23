"""Hesaplama motoru: Aşama I–IV (Eş. 1–28).

Her fonksiyonun docstring'i makaledeki eşitlik numarasını verir. Fonksiyonlar
saf numpy/scipy'dir; form okuma ve raporlama ayrı modüllerdedir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import comb

import numpy as np
from scipy import sparse
from scipy.optimize import linprog

TOL = 1e-9
TIEBREAK_FAILURES = 0      # ikinci aşama (Eş. 21) çözülemeyen problem sayısı


# ===================================================================== Aşama I
def cvr(ne: int, n_experts: int) -> float:
    """Eş. 1: CVR_q = (N^E_q − N/2)/(N/2)."""
    return (ne - n_experts / 2) / (n_experts / 2)


def cvr_critical(n_experts: int, alpha: float = 0.05):
    """Eş. 2: kesin tek yönlü binom testi. Kritik değer yoksa (N ≤ 4) (None, None)."""
    for ne in range(n_experts + 1):
        tail = sum(comb(n_experts, t) for t in range(ne, n_experts + 1)) * 0.5 ** n_experts
        if tail <= alpha + 1e-15:
            return ne, cvr(ne, n_experts)
    return None, None


def stage1(ratings: dict[str, list[str]], essential: str = "Gerekli", alpha: float = 0.05):
    """Her öğe için N^E, CVR ve korunma kararı (Adım 2–3).

    ratings: öğe kodu -> uzmanların değerlendirmeleri (boş yanıtlar çıkarılmış).
    N, öğeyi değerlendiren uzman sayısıdır.
    """
    rows = []
    for q, rs in ratings.items():
        n = len(rs)
        ne = sum(r == essential for r in rs)
        ne_c, cvr_c = cvr_critical(n, alpha) if n else (None, None)
        val = cvr(ne, n) if n else float("nan")
        rows.append(dict(item=q, N=n, NE=ne, CVR=val, NE_crit=ne_c, CVR_crit=cvr_c,
                         retained=(cvr_c is not None and val >= cvr_c - TOL)))
    return rows


# ==================================================================== Aşama II
def applicable_requirements(app: np.ndarray, no_mask: np.ndarray) -> np.ndarray:
    """Eş. 3: 'muhtemelen/kesinlikle uygulanmaz' diyen hukukçu sayısı ≤ H/2 olan gereklilikler.

    app: (H, R) yanıt dizisi; no_mask: aynı şekilde, yanıt 'hayır' türündeyse True.
    """
    H = app.shape[0]
    return no_mask.sum(0) <= H / 2 + TOL


@dataclass
class LegalResult:
    Tbar: np.ndarray      # (m, R) Eş. 4
    Ibar: np.ndarray
    Fbar: np.ndarray
    rmask: np.ndarray     # (R,) ℛ*
    T: np.ndarray         # (m,) Eş. 5
    I: np.ndarray
    F: np.ndarray
    admissible: np.ndarray  # (m,) Eş. 6
    alpha: np.ndarray       # (m,) Eş. 7
    chi: np.ndarray         # (m,) Eş. 31'deki uyum değeri
    notes: list = field(default_factory=list)


def legal_screen(T: np.ndarray, I: np.ndarray, F: np.ndarray, rmask: np.ndarray,
                 tau_F: float, theta: float) -> LegalResult:
    """Eş. 4–7. T, I, F: (H, m, R); eksik değerler NaN (mevcut hukukçuların ortalaması alınır)."""
    notes = []
    if np.isnan(T).any() or np.isnan(I).any() or np.isnan(F).any():
        notes.append("Eksik T/I/F değerleri var; ortalamalar yanıt veren hukukçular üzerinden alındı.")
    Tb, Ib, Fb = np.nanmean(T, 0), np.nanmean(I, 0), np.nanmean(F, 0)
    m = Tb.shape[0]
    if rmask.sum() == 0:
        notes.append("Hiçbir gereklilik uygulanabilir değil (ℛ* boş): tüm düzenler kabul edildi, α = 1.")
        Ti, Ii, Fi = np.ones(m), np.zeros(m), np.zeros(m)
    else:
        Ti = Tb[:, rmask].min(1)
        Ii = Ib[:, rmask].max(1)
        Fi = Fb[:, rmask].max(1)
    adm = Fi < tau_F - TOL
    s = Ti + Ii + Fi
    zero = s <= TOL
    if zero.any():
        notes.append("T + I + F = 0 olan düzen var; uyum değeri θ alındı (tam belirsizlik gibi).")
    chi = np.where(zero, theta, (Ti + theta * Ii) / np.where(zero, 1, s))
    alpha = np.where(adm, chi, 0.0)
    return LegalResult(Tb, Ib, Fb, rmask, Ti, Ii, Fi, adm, alpha, chi, notes)


# =================================================================== Aşama III
@dataclass
class BWMResult:
    weights: np.ndarray
    xi: float
    a_BW: float
    CR: float
    threshold: float | None
    inconsistent: bool
    notes: list = field(default_factory=list)


def liang_threshold(n: int, a_bw: float, table: dict) -> float | None:
    """Liang ve ark. (2020) Tablo 3. a_BW = 2 için eşik 0; a_BW = 1 ve n ≤ 2 için eşik yok."""
    a = int(round(a_bw))
    if a <= 1 or n <= 2:
        return None
    if a == 2:
        return 0.0
    row = table.get(str(min(n, 9)))
    return row[min(a, 9) - 3]


def bwm(best: int, worst: int, a_B: np.ndarray, a_W: np.ndarray, table: dict) -> BWMResult:
    """Eş. 8 (doğrusal BWM, Rezaei 2016) ve Eş. 9 (CR^I, Liang ve ark. 2020).

    a_B[e] = a_Be (en önemlinin e'ye göre önemi), a_W[e] = a_eW (e'nin en önemsize göre önemi).
    """
    n = len(a_B)
    notes = []
    if n == 1:
        return BWMResult(np.ones(1), 0.0, 1.0, 0.0, None, False, notes)
    a_bw = float(a_B[worst])
    if abs(a_W[best] - a_bw) > TOL:
        notes.append(f"a_BW iki satırda farklı ({a_B[worst]:g} ve {a_W[best]:g}); CR için ilk satırdaki değer kullanıldı.")
    # değişkenler: w_0..w_{n-1}, ξ
    rows, b = [], []
    for e in range(n):
        for sgn in (1, -1):
            r = np.zeros(n + 1); r[best] += sgn; r[e] -= sgn * a_B[e]; r[n] = -1; rows.append(r); b.append(0.0)
            r = np.zeros(n + 1); r[e] += sgn; r[worst] -= sgn * a_W[e]; r[n] = -1; rows.append(r); b.append(0.0)
    c = np.zeros(n + 1); c[n] = 1
    res = linprog(c, A_ub=np.array(rows), b_ub=np.array(b), A_eq=np.r_[np.ones(n), 0][None, :], b_eq=[1.0],
                  bounds=[(0, None)] * (n + 1), method="highs")
    if res.status != 0:
        raise RuntimeError(f"BWM LP çözülemedi: {res.message}")
    w = res.x[:n]
    if a_bw <= 1 + TOL:
        cr = 0.0
    else:
        cr = float(np.max(np.abs(a_B * a_W - a_bw)) / (a_bw * (a_bw - 1)))
    thr = liang_threshold(n, a_bw, table)
    return BWMResult(w, float(res.x[n]), a_bw, cr, thr, (thr is not None and cr > thr + TOL), notes)


def global_weights(w_dim: np.ndarray, w_loc: dict[int, np.ndarray], dim_of: np.ndarray) -> np.ndarray:
    """Eş. 10: w_kj = w^dim_kd · w^loc_kj. dim_of[j] = ölçüt j'nin boyut indeksi; w_loc[d] boyut içi sırayla."""
    n = len(dim_of)
    w = np.zeros(n)
    pos = {d: 0 for d in w_loc}
    for j in range(n):
        d = dim_of[j]
        w[j] = w_dim[d] * w_loc[d][pos[d]]
        pos[d] += 1
    return w


def performance(g: np.ndarray, cost: np.ndarray, svn: np.ndarray) -> np.ndarray:
    """Eş. 11–12. g: (..., m, n) 0–10 tam sayı puanlar; svn: (11, 3) Tablo 3."""
    gp = np.where(cost, 10 - g, g).astype(int)                       # Eş. 11
    T, I, F = svn[gp, 0], svn[gp, 1], svn[gp, 2]
    sc = (1 + T - 2 * I - F) / 2                                      # Eş. 12
    return (1 + sc) / 2


def utilities(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Eş. 13: u_ki = Σ_j w_kj x_kij. w: (K, n); x: (K, m, n)."""
    return np.einsum("kj,kij->ki", w, x)


# ==================================================================== Aşama IV
def omega_from_power(p: np.ndarray) -> np.ndarray:
    """Eş. 14."""
    return p / p.sum()


def consensus_levels(U: np.ndarray, omega: np.ndarray) -> np.ndarray:
    """Eş. 15–16: CL_k = 1 − (1/m) Σ_i |u_ki − u_ci|."""
    uc = omega @ U
    return 1 - np.abs(U - uc).mean(1)


def gamma_threshold(U: np.ndarray, omega: np.ndarray, pi: float) -> float:
    """Eş. 16: başlangıç uzlaşı düzeylerinin π'inci yüzdeliği (doğrusal ara değer, Hyndman–Fan tip 7)."""
    return float(np.percentile(consensus_levels(U, omega), pi))


class ConsensusLP:
    """Eş. 15–21'in doğrusal programı. Değişkenler: û (K·m), η (K·m), ε (K·m)."""

    def __init__(self, omega: np.ndarray, m: int):
        K = len(omega)
        self.K, self.m, self.N = K, m, K * m
        N = self.N
        idx = np.arange(N).reshape(K, m)
        r, c, v = [], [], []
        row = 0
        # (1) û − η ≤ u ; (2) −û − η ≤ −u
        for sgn in (1, -1):
            r += list(row + np.arange(N)); c += list(idx.ravel()); v += [sgn] * N
            r += list(row + np.arange(N)); c += list(N + idx.ravel()); v += [-1] * N
            row += N
        # (3) û_ki − Σ_l ω_l û_li − ε_ki ≤ 0 ; (4) −(...) − ε_ki ≤ 0
        for sgn in (1, -1):
            for k in range(K):
                for i in range(m):
                    for l in range(K):
                        coef = (1.0 if l == k else 0.0) - omega[l]
                        if coef != 0:
                            r.append(row); c.append(idx[l, i]); v.append(sgn * coef)
                    r.append(row); c.append(2 * N + idx[k, i]); v.append(-1)
                    row += 1
        # (5) (1/m) Σ_i ε_ki ≤ 1 − γ
        for k in range(K):
            for i in range(m):
                r.append(row); c.append(2 * N + idx[k, i]); v.append(1 / m)
            row += 1
        self.A = sparse.csr_matrix((v, (r, c)), shape=(row, 3 * N))
        self.n_rows = row
        self.idx = idx

    def solve(self, U: np.ndarray, gamma: float, cost: np.ndarray | None = None,
              L: np.ndarray | None = None, minimize_L: bool = False,
              cap_L: float | None = None, cap_total: float | None = None, tiebreak: bool = True):
        K, m, N = self.K, self.m, self.N
        b = np.r_[U.ravel(), -U.ravel(), np.zeros(2 * N), np.full(K, 1 - gamma)]
        A = self.A
        extra_rows, extra_b = [], []
        if cap_L is not None:
            r = np.zeros(3 * N); r[N + self.idx[L].ravel()] = 1; extra_rows.append(r); extra_b.append(cap_L)
        if cap_total is not None:
            r = np.zeros(3 * N); r[N:2 * N] = 1; extra_rows.append(r); extra_b.append(cap_total)
        if extra_rows:
            A = sparse.vstack([A, sparse.csr_matrix(np.array(extra_rows))]).tocsr()
            b = np.r_[b, extra_b]
        c = np.zeros(3 * N)
        if minimize_L:
            c[N + self.idx[L].ravel()] = 1
        else:
            c[N:2 * N] = np.repeat(cost, m)
        bounds = [(0, 1)] * N + [(0, None)] * (2 * N)
        res = linprog(c, A_ub=A, b_ub=b, bounds=bounds, method="highs")
        if res.status != 0:
            raise RuntimeError(f"Uzlaşı LP çözülemedi: {res.message}")
        x = res.x
        if tiebreak:
            x = self._tiebreak(U, A, b, c, float(res.fun), x)
        Uh = np.clip(x[:N], 0, 1).reshape(K, m)
        return Uh, float(res.fun)

    def _tiebreak(self, U, A, b, c, fstar, x_lp):
        """Eş. 21'in ikinci kısmı: en iyi çözümler arasında Σ(û − u)²'yi en küçük yapan tek çözüm.

        min ½‖û − u‖²  s.t.  modelin kısıtları,  cᵀx ≤ f*(1 + 1e-7) + 1e-9.
        Clarabel (iç nokta, QP). Çözücü yoksa ya da çözemezse LP çözümü döner ve bayrak kalkar.
        """
        global TIEBREAK_FAILURES
        try:
            import clarabel
        except ImportError:
            TIEBREAK_FAILURES += 1
            return x_lp
        N, n = self.N, 3 * self.N
        u = U.ravel()
        P = sparse.diags(np.r_[np.ones(N), np.zeros(2 * N)]).tocsc()
        q = np.r_[-u, np.zeros(2 * N)]
        I = sparse.identity(n, format="csr")
        Aq = sparse.vstack([A, sparse.csr_matrix(c[None, :]), I[:N], -I]).tocsc()
        bq = np.r_[b, fstar * (1 + 1e-7) + 1e-9, np.ones(N), np.zeros(n)]
        st = clarabel.DefaultSettings()
        st.verbose = False
        sol = clarabel.DefaultSolver(P, q, Aq, bq, [clarabel.NonnegativeConeT(Aq.shape[0])], st).solve()
        if "Solved" not in str(sol.status):
            TIEBREAK_FAILURES += 1
            return x_lp
        return np.asarray(sol.x)


@dataclass
class ModelResult:
    name: str
    Uhat: np.ndarray       # (K, m)
    uc: np.ndarray         # (m,) Eş. 15
    beta: np.ndarray       # (K,) Eş. 17
    CL: np.ndarray         # (K,)
    objective: float


def run_models(U: np.ndarray, p: np.ndarray, L: np.ndarray, gamma: float, delta: float,
               omega: np.ndarray | None = None, lp: ConsensusLP | None = None,
               which=("M0", "M1", "M2"), m0_solution: bool = True) -> dict[str, ModelResult]:
    """Adım 15–17: M1 (Eş. 18), M0 (Eş. 19), M2 (Eş. 20)."""
    omega = omega_from_power(p) if omega is None else omega
    lp = lp or ConsensusLP(omega, U.shape[1])
    out = {}

    def pack(name, Uh, obj):
        uc = omega @ Uh
        return ModelResult(name, Uh, uc, np.abs(Uh - U).sum(1), 1 - np.abs(Uh - uc).mean(1), obj)

    if "M1" in which:
        Uh, f = lp.solve(U, gamma, cost=p)
        out["M1"] = pack("M1", Uh, f)
    if "M0" in which or "M2" in which:
        has_L = L.any() and not L.all()
        Uh0, Z0 = lp.solve(U, gamma, cost=np.ones(len(p)), tiebreak=m0_solution and not has_L)
        if has_L:
            Uh0b, bL0 = lp.solve(U, gamma, L=L, minimize_L=True, cap_total=Z0 * (1 + 1e-9) + 1e-10,
                                 tiebreak=m0_solution)
        else:
            Uh0b, bL0 = Uh0, float(np.abs(Uh0 - U)[L].sum()) if L.any() else 0.0
        out["M0"] = pack("M0", Uh0b, Z0)
        out["M0"].Z0, out["M0"].beta_L0 = Z0, bL0
        if "M2" in which:
            if has_L:
                Uh2, f2 = lp.solve(U, gamma, cost=p, L=L, cap_L=(1 + delta) * bL0 * (1 + 1e-9) + 1e-10)
            else:
                Uh2, f2 = lp.solve(U, gamma, cost=p)
            out["M2"] = pack("M2", Uh2, f2)
    return out


def frac_rank(x: np.ndarray) -> np.ndarray:
    """Eş. 24'teki kesirli sıra (o_k − 1/2)/K; eşit güçlere ortalama sıra."""
    from scipy.stats import rankdata
    return (rankdata(x, method="average") - 0.5) / len(x)


def diagnostics(models: dict[str, ModelResult], p: np.ndarray, L: np.ndarray) -> dict:
    """Eş. 23–25; paydalar sıfırsa göstergeler sıfır."""
    out = {}
    for name, r in models.items():
        tot = r.beta.sum()
        lps = float(r.beta[L].sum() / tot) if tot > TOL else 0.0
        mu = r.beta.mean()
        cb = float(2 / mu * np.cov(r.beta, frac_rank(p), bias=True)[0, 1]) if mu > TOL else 0.0
        out[name] = dict(LPS=lps, C_beta=cb, total_burden=float(tot), weighted_burden=float(p @ r.beta))
    if "M1" in models and "M2" in models:
        d1, d2 = p @ models["M1"].beta, p @ models["M2"].beta
        out["CoP"] = float((d2 - d1) / d1) if d1 > TOL else 0.0
    return out


def group_scores(alpha: np.ndarray, uc: np.ndarray, adm: np.ndarray) -> np.ndarray:
    """Eş. 22: V_i = α_i û_ci (kabul edilmeyenler NaN)."""
    return np.where(adm, alpha * uc, np.nan)


def top_of(scores: np.ndarray, mask: np.ndarray | None = None, ascending: bool = False):
    """En iyi düzenin indeksi ve eşitlik olup olmadığı."""
    s = np.where(np.isnan(scores), np.inf if ascending else -np.inf, scores)
    if mask is not None:
        s = np.where(mask, s, np.inf if ascending else -np.inf)
    best = np.min(s) if ascending else np.max(s)
    ties = np.where(np.abs(s - best) <= 1e-9)[0]
    return int(ties[0]), len(ties) > 1


def voice_weights(p: np.ndarray, L: np.ndarray, s: float) -> np.ndarray:
    """Eş. 27."""
    w = np.empty(len(p))
    w[L] = s / L.sum()
    w[~L] = (1 - s) * p[~L] / p[~L].sum()
    return w


def voice_threshold(U: np.ndarray, p: np.ndarray, L: np.ndarray, gamma: float, delta: float,
                    alpha: np.ndarray, adm: np.ndarray, grid: np.ndarray, model: str = "M2"):
    """Eş. 26–28. Döndürür: i_L, s* (bulunamazsa None) ve ızgaradaki en iyi düzenler."""
    if not L.any() or L.all() or not adm.any():
        return dict(i_L=None, s_star=None, tops=[], note="Ses eşiği tanımsız (L boş, herkes L'de ya da kabul edilen düzen yok).")
    i_L, tie = top_of(np.where(adm, alpha * U[L].mean(0), np.nan))   # Eş. 26 (α ile, Eş. 22 gibi)
    tops = []
    for s in grid:
        om = voice_weights(p, L, float(s))
        res = run_models(U, p, L, gamma, delta, omega=om, lp=ConsensusLP(om, U.shape[1]),
                         which=("M0", "M2") if model == "M2" else ("M1",), m0_solution=False)
        t, _ = top_of(group_scores(alpha, res[model].uc, adm))
        tops.append(t)
    return dict(i_L=i_L, i_L_tie=tie, tops=tops, **voice_stats(tops, i_L, grid))


def voice_stats(tops, i_L, grid):
    """Eş. 28: s* (ilk kazanılan ağırlık), s^st (sonrasında hep kazanılan ilk ağırlık), φ_L (kazanılan pay)."""
    wins = [t == i_L for t in tops]
    s_star = next((float(s) for s, w in zip(grid, wins) if w), None)
    s_st = None
    if wins and wins[-1]:
        k = len(wins) - 1
        while k > 0 and wins[k - 1]:
            k -= 1
        s_st = float(grid[k])
    return dict(s_star=s_star, s_stable=s_st, share=float(np.mean(wins)) if wins else 0.0)
