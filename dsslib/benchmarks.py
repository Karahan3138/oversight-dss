"""Karşılaştırma yöntemleri (Ek B, Eş. B.1–B.14).

Her yöntem genel biçimde yazıldı: `cost` maliyet ölçütlerini gösterir. Boru hattı ilk beş
yönteme cost = boş verir; bu durumda formüller Ek B'deki fayda biçimine indirgenir.
Genel biçim, yayımlanmış sayısal örneklerle doğrulama yapabilmek içindir.
Düz ölçüt (x⁺ = x⁻) kuralı: normalleştirilmiş değerler sıfırdır (Ek B).
"""
from __future__ import annotations

import numpy as np

EPS = 1e-12


def _flat(X):
    return (X.max(0) - X.min(0)) <= EPS


def topsis(X, w, cost=None):
    """Eş. B.1–B.2; büyük CC daha iyi."""
    cost = np.zeros(X.shape[1], bool) if cost is None else cost
    norm = np.sqrt((X ** 2).sum(0))
    Z = np.divide(X, norm, out=np.zeros_like(X), where=norm > EPS)
    Z[:, _flat(X)] = 0.0
    V = w * Z
    vp = np.where(cost, V.min(0), V.max(0))
    vm = np.where(cost, V.max(0), V.min(0))
    Ep = np.sqrt(((V - vp) ** 2).sum(1))
    Em = np.sqrt(((V - vm) ** 2).sum(1))
    den = Ep + Em
    return np.divide(Em, den, out=np.full(len(X), 0.5), where=den > EPS)


def vikor(X, w, lam=0.5, cost=None):
    """Eş. B.3–B.4; küçük Q daha iyi. Döndürür: Q, S, R."""
    cost = np.zeros(X.shape[1], bool) if cost is None else cost
    best = np.where(cost, X.min(0), X.max(0))
    worst = np.where(cost, X.max(0), X.min(0))
    rng = best - worst
    D = np.divide(best - X, rng, out=np.zeros_like(X), where=np.abs(rng) > EPS)
    S = (w * D).sum(1)
    R = (w * D).max(1)

    def mm(a):
        r = a.max() - a.min()
        return (a - a.min()) / r if r > EPS else np.zeros_like(a)
    Q = lam * mm(S) + (1 - lam) * mm(R)
    return Q, S, R


def waspas(X, w, lam=0.5, cost=None):
    """Eş. B.5; büyük Q daha iyi."""
    cost = np.zeros(X.shape[1], bool) if cost is None else cost
    Z = np.where(cost, np.divide(X.min(0), X, out=np.zeros_like(X), where=X > EPS),
                 np.divide(X, X.max(0), out=np.zeros_like(X), where=X.max(0) > EPS))
    Z[:, _flat(X)] = 0.0
    wsm = (w * Z).sum(1)
    wpm = np.prod(np.power(Z, w), axis=1)
    return lam * wsm + (1 - lam) * wpm


def _minmax(X, cost):
    mx, mn = X.max(0), X.min(0)
    rng = mx - mn
    Z = np.where(cost, (mx - X), (X - mn))
    Z = np.divide(Z, rng, out=np.zeros_like(X), where=rng > EPS)
    return Z


def cocoso(X, w, lam=0.5, cost=None):
    """Eş. B.6–B.8; büyük σ daha iyi.

    Uygulama kuralı: bir düzen her ölçütte en kötüyse S ya da P en küçük değeri 0 olur ve
    σ_ib tanımsızdır; bu durumda payda olarak en küçük pozitif değer kullanılır.
    """
    cost = np.zeros(X.shape[1], bool) if cost is None else cost
    Z = _minmax(X, cost)
    S = (w * Z).sum(1)
    P = np.power(Z, w).sum(1)
    ka = (P + S) / (P + S).sum()

    def pmin(a):
        pos = a[a > EPS]
        return pos.min() if len(pos) else 1.0
    kb = S / pmin(S) + P / pmin(P)
    kc = (lam * S + (1 - lam) * P) / (lam * S.max() + (1 - lam) * P.max())
    return np.cbrt(ka * kb * kc) + (ka + kb + kc) / 3


def mabac(X, w, cost=None):
    """Eş. B.9; büyük S daha iyi."""
    cost = np.zeros(X.shape[1], bool) if cost is None else cost
    Z = _minmax(X, cost)
    V = w * (Z + 1)
    G = np.exp(np.log(V).mean(0))          # geometrik ortalama (BAA_j)
    return (V - G).sum(1)


def arlon(X, w, cost, zeta=0.5, scale=True):
    """Eş. B.10–B.14; büyük Q daha iyi.

    X: maliyet ölçütleri özgün yönünde (x^o). scale=True ise x^AR = 1 + 100 x^o (Eş. B.10);
    yayımlanmış örneklerle karşılaştırmada scale=False verilir.
    """
    XA = 1 + 100 * X if scale else X.astype(float)
    m = XA.shape[0]
    ln, l2 = np.log(XA), np.log2(XA)
    s1, s2 = ln.sum(0), l2.sum(0)
    r1 = np.divide(ln, s1, out=np.zeros_like(XA), where=np.abs(s1) > EPS)
    r2 = np.divide(l2, s2, out=np.zeros_like(XA), where=np.abs(s2) > EPS)
    Z1 = np.where(cost, (1 - r1) / (m - 1), r1)                    # Eş. B.11
    Z2 = np.where(cost, 1 - r2, r2)                                 # Eş. B.12
    flat = _flat(XA)
    Z1[:, flat] = 0.0
    Z2[:, flat] = 0.0
    Z = (1 - zeta) * np.sqrt(Z1 * Z2) + zeta * (Z1 + Z2) / 2        # Eş. B.13
    V = w * Z
    Sp, Sm = V[:, ~cost].sum(1), V[:, cost].sum(1)
    psi = (~cost).sum() / len(cost)
    return np.power(Sp, psi) + np.power(Sm, 1 - psi)               # Eş. B.14


def all_methods(Xc, wc, cost, params):
    """Adım 21: altı yöntemin puanı ve sıralama yönü (True = büyük iyi)."""
    none = np.zeros(Xc.shape[1], bool)
    Xo = np.where(cost, 1 - Xc, Xc)                                 # Eş. B.10 (x^o)
    q, _, _ = vikor(Xc, wc, params["vikor_lambda"], none)
    return {
        "TOPSIS": (topsis(Xc, wc, none), True),
        "VIKOR": (q, False),
        "WASPAS": (waspas(Xc, wc, params["waspas_lambda"], none), True),
        "CoCoSo": (cocoso(Xc, wc, params["cocoso_lambda"], none), True),
        "MABAC": (mabac(Xc, wc, none), True),
        "ARLON": (arlon(Xo, wc, cost, params["arlon_zeta"]), True),
    }
