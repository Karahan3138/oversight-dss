"""Aşama II hukukçu formu ve Aşama III karar verici formu. Kullanım: python build_forms.py [çıktı klasörü]"""
import os
import sys
import json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "blank")
os.makedirs(OUT, exist_ok=True)
CFG = json.load(open(os.path.join(os.path.dirname(HERE), "config.json"), encoding="utf-8"))
TEAM = CFG["forms"]["team"]
PRIVACY = CFG["forms"]["privacy"]
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter as L
from style import BODY, BOLD, TITLE, INPUT_FILL, BORDER, TOP_WRAP, header, ARIAL

EX_FONT = Font(name=ARIAL, size=10, italic=True, color="808080")
EX_FILL = PatternFill("solid", fgColor="F2F2F2")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

ALTS = [(a["code"], a["name"], a["definition"]) for a in CFG["alternatives"]]
REQS = [(q["code"], q["source"], q["definition"]) for q in CFG["requirements"]]
TYPE_TR = {"benefit": "fayda", "cost": "maliyet"}
CRITS = [(c["code"], c["code"], c["name"], TYPE_TR[c["type"]], c["definition"]) for c in CFG["criteria"]]
DIMS = [(d["code"], d["name"], d["criteria"]) for d in CFG["dimensions"]]


def code_range(codes):
    """['C1','C2','C3'] -> 'C1–C3' if consecutive, else comma list."""
    if not codes:
        return ""
    nums = [int(c[1:]) for c in codes]
    if nums == list(range(nums[0], nums[0] + len(nums))):
        return codes[0] if len(codes) == 1 else f"{codes[0]}–{codes[-1]}"
    return ", ".join(codes)


BEN = code_range([c[0] for c in CRITS if c[3] == "fayda"])
COST = code_range([c[0] for c in CRITS if c[3] == "maliyet"])
NA, NR = len(ALTS), len(REQS)
def qlist(xs):
    return '"' + ",".join(str(x) for x in xs) + '"'



def guide_sheet(ws, rows):
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 24, 105
    for i, (a, b) in enumerate(rows, 1):
        ca, cb = ws.cell(row=i, column=1, value=a), ws.cell(row=i, column=2, value=b)
        ca.font = TITLE if i == 1 else BOLD
        cb.font = BOLD if i == 1 else BODY
        ca.alignment = cb.alignment = TOP_WRAP
        ws.row_dimensions[i].height = 18 if len(b or "") < 100 else 15 * (len(b) // 98 + 1)
    ws.page_setup.orientation = "landscape"; ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0


def cell(ws, r, c, v=None, font=BODY, fill=None, border=True, align=TOP_WRAP):
    x = ws.cell(row=r, column=c, value=v); x.font = font; x.alignment = align
    if border: x.border = BORDER
    if fill: x.fill = fill
    return x


def def_table(ws, r0, title, items, cols):
    cell(ws, r0, 1, title, BOLD, border=False)
    header(ws, r0 + 1, cols)
    for i, it in enumerate(items, r0 + 2):
        for j, v in enumerate(it, 1):
            cell(ws, i, j, v)
        ws.row_dimensions[i].height = 15 * (len(it[-1]) // 80 + 1)
    return r0 + 2 + len(items)


# ================================================================ HUKUKÇU FORMU
wb = Workbook()
y = wb.active; y.title = "Yönerge"
guide_sheet(y, [
    ("Hukukçu formu", "YZ destekli performans değerlendirmesinde insan denetimi düzenlerinin hukuki statüsü"),
    ("Katılımcı kodu", "[KOD]"),
    ("Uygulayan", TEAM),
    ("Amaç", f"Bir firmanın YZ destekli performans değerlendirmesinde kullanabileceği {NA} insan denetimi düzeninin, {NR} hukuki gereklilik karşısındaki statüsünü değerlendirmenizi istiyoruz. Bu değerlendirmeler, karar destek sisteminde hukuka açıkça aykırı düzenleri eleyen ve hukuki belirsizliği ayrıca hesaba katan bir katmanın girdisi olacak."),
    ("Vaka firması", "[Firma adı, sektörü, çalışan sayısı ve AB bağlantısı firma belirlendiğinde buraya yazılacak.]"),
    ("Adım 1", "'Uygulanabilirlik' sayfasında her gerekliliğin vaka firmasına uygulanıp uygulanmadığını belirtin. Örneğin AI Act ve GDPR'nin AB bağlantısı olmayan bir Türk firmasına uygulanması kesin olmayabilir."),
    ("Adım 2", "'Değerlendirme' sayfasında her düzen ve gereklilik çifti için üç değeri ayrı ayrı verin: T, I ve F. Uygulanabilirlik belirsizse bunu I'ya yansıtın."),
    ("T", "Düzenin gerekliliği karşılama derecesi."),
    ("I", "Hukuki belirsizlik derecesi: yorum farkı, içtihat eksikliği, düzenlemenin yürürlük takvimi ya da firmaya uygulanabilirliğin belirsizliği."),
    ("F", "Düzenin gerekliliği ihlal etme derecesi."),
    ("Ölçek", "Her biri için: 0 = yok, 0,25 = düşük, 0,5 = orta, 0,75 = yüksek, 1 = tam. T, I ve F birbirinden bağımsızdır; toplamlarının 1 olması gerekmez."),
    ("Kısa gerekçe", "Her satır için bir cümlelik gerekçe yazmanız, hukukçular arası görüş ayrılıklarını yorumlamamıza yardımcı olur."),
    ("Süre", "Yaklaşık 45–60 dakika."),
    ("Gizlilik ve analiz", PRIVACY),
])
r = 16
cell(y, r, 1, "Denetim düzenleri", BOLD, border=False)
for i, a_ in enumerate(ALTS, r + 1):
    cell(y, i, 1, a_[0]); cell(y, i, 2, f"{a_[1]}: {a_[2]}"); y.row_dimensions[i].height = 30
r = r + 1 + len(ALTS) + 1
cell(y, r, 1, "Hukuki gereklilikler", BOLD, border=False)
for i, q_ in enumerate(REQS, r + 1):
    cell(y, i, 1, f"{q_[0]} {q_[1]}"); cell(y, i, 2, q_[2]); y.row_dimensions[i].height = 30

u = wb.create_sheet("Uygulanabilirlik")
for col, w in zip("ABCD", (8, 22, 26, 70)):
    u.column_dimensions[col].width = w
header(u, 1, [("Kod", 8), ("Gereklilik", 22), ("Vaka firmasına uygulanır mı?", 26), ("Gerekçe", 70)])
dvu = DataValidation(type="list", formula1=qlist(CFG["applicability_scale"]), allow_blank=True)
u.add_data_validation(dvu)
for i, (k, ad, _) in enumerate(REQS, 2):
    cell(u, i, 1, k); cell(u, i, 2, ad)
    cell(u, i, 3, fill=INPUT_FILL); cell(u, i, 4, fill=INPUT_FILL)
    dvu.add(f"C{i}"); u.row_dimensions[i].height = 30

d = wb.create_sheet("Değerlendirme")
cols = [("No", 5), ("Düzen", 30), ("Gereklilik", 16), ("T (karşılama)", 11), ("I (belirsizlik)", 11), ("F (ihlal)", 11), ("Kısa gerekçe", 60), ("Kontrol", 16)]
CHECK_FONT = Font(name=ARIAL, size=10, bold=True, color="C00000")
header(d, 1, cols)
for j, (_, w) in enumerate(cols, 1):
    d.column_dimensions[L(j)].width = w
ex = ["Örnek", "A2 YZ önerir, yönetici karar verir", "R4 GDPR m.22(3)", 0.5, 0.75, 0.25, "Yönetici öneriyi fiilen onaylıyorsa karar SCHUFA'ya göre otomatik sayılabilir."]
for j, v in enumerate(ex, 1):
    c = cell(d, 2, j, v, EX_FONT, EX_FILL)
dvs = DataValidation(type="list", formula1=qlist(CFG["legal_scale"]), allow_blank=True); d.add_data_validation(dvs)
k = 0
for a in ALTS:
    for q in REQS:
        k += 1; rr = k + 2
        cell(d, rr, 1, k); cell(d, rr, 2, f"{a[0]} {a[1]}"); cell(d, rr, 3, f"{q[0]} {q[1]}")
        for j in (4, 5, 6):
            c = cell(d, rr, j, fill=INPUT_FILL, align=CENTER); c.number_format = "0.00"
        cell(d, rr, 7, fill=INPUT_FILL)
        cell(d, rr, 8, f'=IF(COUNT(D{rr}:F{rr})=3,"","T, I ve F girin")', CHECK_FONT)
        dvs.add(f"D{rr}:F{rr}")
d.freeze_panes = "D3"
for ws_ in (u, d):
    ws_.page_setup.orientation = "landscape"; ws_.sheet_properties.pageSetUpPr.fitToPage = True
    ws_.page_setup.fitToWidth, ws_.page_setup.fitToHeight = 1, 0
d.print_title_rows = "1:1"
p1 = f"{OUT}/Hukukcu_Formu.xlsx"; wb.save(p1)

# ================================================================ KARAR VERİCİ FORMU
wb = Workbook()
y = wb.active; y.title = "Yönerge"
guide_sheet(y, [
    ("Karar verici formu", "YZ destekli performans değerlendirmesinde insan denetimi düzeni seçimi"),
    ("Katılımcı kodu", "[KOD]"),
    ("Uygulayan", TEAM),
    ("Amaç", "Firmanızın YZ destekli performans değerlendirmesinde hangi insan denetimi düzenini kullanacağına birlikte karar vermenizi destekleyen bir sistem kullanıyoruz. Sizden iki şey istiyoruz: ölçütlerin sizin için önemi ve her düzenin her ölçütteki performansı."),
    ("Doğru ya da yanlış yanıt yok", "Kendi görüşünüzü yansıtın. Gruplar arasındaki görüş farkları bu çalışmanın konusudur."),
    ("Bölüm 1: Bilgiler", "'Bilgiler' sayfasında grubunuzu, kademenizi ve kıdeminizi seçin."),
    ("Bölüm 2: Önem", "'Önem' sayfasında önce üç boyutu, sonra her boyutun içindeki ölçütleri karşılaştırın. Her grupta en önemli ve en önemsiz öğeyi seçin; sonra en önemlinin diğerlerine göre kaç kat önemli olduğunu ve diğerlerinin en önemsize göre kaç kat önemli olduğunu 1–9 arasında yazın (1 = eşit, 9 = son derece daha önemli)."),
    ("Bölüm 3: Değerlendirme", f"'Değerlendirme' sayfasında her düzeni her ölçüt için 0–10 arasında puanlayın. Fayda ölçütlerinde 10 son derece iyi, 0 son derece kötü demektir. Maliyet ölçütlerinde ({COST}) puan yükün ya da riskin büyüklüğünü gösterir: 0 yok, 10 son derece yüksek. Puanların sözel karşılıkları 'Ölçek' sayfasında. Her düzenin sizin firmanızda uygulandığında nasıl işleyeceğini düşünerek puanlayın."),
    ("Süre", "Yaklaşık 30–40 dakika."),
    ("Gizlilik ve analiz", PRIVACY),
])
r = 12
cell(y, r, 1, "Denetim düzenleri", BOLD, border=False)
for i, a in enumerate(ALTS, r + 1):
    cell(y, i, 1, a[0]); cell(y, i, 2, f"{a[1]}: {a[2]}"); y.row_dimensions[i].height = 30
r = r + 1 + len(ALTS) + 1
cell(y, r, 1, "Ölçütler", BOLD, border=False)
for i, c_ in enumerate(CRITS, r + 1):
    cell(y, i, 1, f"{c_[0]} ({c_[3]})"); cell(y, i, 2, f"{c_[2]}: {c_[4]}"); y.row_dimensions[i].height = 30
r = r + 1 + len(CRITS) + 1
cell(y, r, 1, "Boyutlar", BOLD, border=False)
for i, dd in enumerate(DIMS, r + 1):
    cell(y, i, 1, dd[0]); cell(y, i, 2, f"{dd[1]}: {', '.join(dd[2])}")

b = wb.create_sheet("Bilgiler")
b.column_dimensions["A"].width, b.column_dimensions["B"].width = 32, 40
info = [("Grubunuz", qlist(CFG["groups"])),
        ("Örgütteki kademeniz", qlist([lv["name"] for lv in CFG["levels"]])),
        ("Firmadaki kıdeminiz", qlist(CFG["tenure"]))]
for i, (lab, lst) in enumerate(info, 1):
    cell(b, i, 1, lab, BOLD); c = cell(b, i, 2, fill=INPUT_FILL)
    if lst == "whole":
        dv = DataValidation(type="whole", operator="between", formula1="0", formula2="50", allow_blank=True)
    elif lst:
        dv = DataValidation(type="list", formula1=lst, allow_blank=True)
    else:
        continue
    b.add_data_validation(dv); dv.add(c.coordinate)

s = wb.create_sheet("Ölçek")
s.column_dimensions["A"].width, s.column_dimensions["B"].width, s.column_dimensions["C"].width = 8, 26, 34
header(s, 1, [("Puan", 8), (f"Fayda ölçütleri ({BEN})", 26), (f"Maliyet ölçütleri ({COST})", 34)])
good = CFG["rating_scale"]["benefit_labels"]
cost = CFG["rating_scale"]["cost_labels"]
for v in range(11):
    cell(s, v + 2, 1, v, align=CENTER); cell(s, v + 2, 2, good[v]); cell(s, v + 2, 3, cost[v])
cell(s, 14, 1, "Önem karşılaştırmasında 1 = eşit önemde, 3 = biraz daha önemli, 5 = belirgin biçimde daha önemli, 7 = çok daha önemli, 9 = son derece daha önemli; 2, 4, 6, 8 ara değerler.", border=False)
s.merge_cells("A14:C16"); s.row_dimensions[14].height = 30

o = wb.create_sheet("Önem")
o.column_dimensions["A"].width = 46
for j in range(2, 7):
    o.column_dimensions[L(j)].width = 15
cell(o, 1, 1, "Her blokta önce en önemli ve en önemsiz öğeyi seçin, sonra 1–9 arası sayıları yazın. Gri blok örnektir.", BOLD, border=False)
o.merge_cells("A1:F1")
dv19 = DataValidation(type="whole", operator="between", formula1="1", formula2="9", allow_blank=True)
o.add_data_validation(dv19)


def bwm_block(r, title, elems, example=None):
    lst = '"' + ",".join(elems) + '"'
    font, fill = (EX_FONT, EX_FILL) if example else (BOLD, None)
    cell(o, r, 1, title, BOLD if not example else EX_FONT, fill, border=False)
    labs = ["En önemli öğe", "En önemsiz öğe"]
    for k, lab in enumerate(labs):
        cell(o, r + 1 + k, 1, lab, BODY if not example else EX_FONT, fill)
        c = cell(o, r + 1 + k, 2, example[k] if example else None, BODY if not example else EX_FONT, EX_FILL if example else INPUT_FILL)
        if not example:
            dv = DataValidation(type="list", formula1=lst, allow_blank=True); o.add_data_validation(dv); dv.add(c.coordinate)
    rr = r + 3
    cell(o, rr, 1, "Öğe", BOLD if not example else EX_FONT, fill)
    for j, e in enumerate(elems, 2):
        cell(o, rr, j, e, BOLD if not example else EX_FONT, fill, align=CENTER)
    cell(o, rr + 1, 1, "En önemli öğe, bu öğeden kaç kat daha önemli? (en önemlinin kendisi için 1)", BODY if not example else EX_FONT, fill)
    cell(o, rr + 2, 1, "Bu öğe, en önemsiz öğeden kaç kat daha önemli? (en önemsizin kendisi için 1)", BODY if not example else EX_FONT, fill)
    for j in range(2, 2 + len(elems)):
        for k in (1, 2):
            v = example[2 + (k - 1) * len(elems) + (j - 2)] if example else None
            c = cell(o, rr + k, j, v, BODY if not example else EX_FONT, EX_FILL if example else INPUT_FILL, align=CENTER)
            if not example:
                dv19.add(c.coordinate)
    o.row_dimensions[rr + 1].height = o.row_dimensions[rr + 2].height = 30
    if example:
        return rr + 4
    last = L(1 + len(elems))
    hdr, bo, ow = (f"$B${rr + k}:${last}${rr + k}" for k in (0, 1, 2))
    best, worst = f"$B${r + 1}", f"$B${r + 2}"
    f = (f'=IF(COUNTA({best},{worst})<2,"En önemli ve en önemsiz öğeyi seçin",'
         f'IF({best}={worst},"Uyarı: en önemli ve en önemsiz öğe aynı olamaz",'
         f'IF(COUNT({bo})+COUNT({ow})<{2 * len(elems)},"Tüm hücrelere 1–9 arası bir sayı yazın",'
         f'IF(INDEX({bo},MATCH({best},{hdr},0))<>1,"Uyarı: en önemli öğenin kendisi için 1 yazın",'
         f'IF(INDEX({ow},MATCH({worst},{hdr},0))<>1,"Uyarı: en önemsiz öğenin kendisi için 1 yazın",'
         f'IF(INDEX({bo},MATCH({worst},{hdr},0))<>INDEX({ow},MATCH({best},{hdr},0)),'
         f'"Uyarı: en önemli ile en önemsiz arasındaki değer iki satırda aynı olmalı","Tamam"))))))')
    cell(o, rr + 3, 1, "Kontrol", BOLD)
    c = cell(o, rr + 3, 2, f, CHECK_FONT)
    o.merge_cells(start_row=rr + 3, start_column=2, end_row=rr + 3, end_column=1 + len(elems))
    return rr + 5


ex = ["Fiyat", "Renk", 1, 2, 8, 8, 4, 1]  # örnek: tutarlı (2 × 4 = 8)
r = bwm_block(3, "Örnek: bir araba seçiminde Fiyat, Kalite, Renk", ["Fiyat", "Kalite", "Renk"], ex)
r = bwm_block(r, "Blok 1: Boyutlar", [f"{dd[0]} {dd[1]}" for dd in DIMS])
for dd in DIMS:
    names = {c_[0]: c_[2] for c_ in CRITS}
    r = bwm_block(r, f"Blok: {dd[0]} {dd[1]} içindeki ölçütler", [f"{c} {names[c]}" for c in dd[2]])

v = wb.create_sheet("Değerlendirme")
v.column_dimensions["A"].width = 34
cell(v, 1, 1, f"Her düzeni her ölçüt için 0–10 arasında puanlayın. {BEN} ölçütlerinde yüksek puan iyi; {COST} ölçütlerinde yüksek puan yükün ya da riskin büyük olduğu anlamına gelir.", BOLD, border=False)
v.merge_cells(start_row=1, start_column=1, end_row=1, end_column=1 + len(CRITS))
v.row_dimensions[1].height = 30
cell(v, 2, 1, "Düzen", BOLD, align=CENTER)
for j, c_ in enumerate(CRITS, 2):
    anchor = "0 kötü – 10 iyi" if c_[3] == "fayda" else "0 yok – 10 çok yüksek"
    cell(v, 2, j, f"{c_[0]} {c_[2]}\n({anchor})", BOLD, align=CENTER)
    v.column_dimensions[L(j)].width = 14
v.row_dimensions[2].height = 58
dv010 = DataValidation(type="whole", operator="between", formula1="0", formula2="10", allow_blank=True)
v.add_data_validation(dv010)
cell(v, 3, 1, "Örnek: A0 Kâğıt formla değerlendirme", EX_FONT, EX_FILL)
EXV = [6, 7, 3, 5, 4, 2, 1, 8, 9, 3]
for j, val in enumerate((EXV * 3)[:len(CRITS)], 2):
    cell(v, 3, j, val, EX_FONT, EX_FILL, align=CENTER)
for i, a in enumerate(ALTS, 4):
    cell(v, i, 1, f"{a[0]} {a[1]}")
    for j in range(2, 2 + len(CRITS)):
        cell(v, i, j, fill=INPUT_FILL, align=CENTER); dv010.add(v.cell(row=i, column=j).coordinate)
    lc = L(1 + len(CRITS))
    cell(v, i, 2 + len(CRITS), f'=IF(COUNT(B{i}:{lc}{i})={len(CRITS)},"","Eksik puan var")', CHECK_FONT)
    v.row_dimensions[i].height = 22
cell(v, 2, 2 + len(CRITS), "Kontrol", BOLD, align=CENTER); v.column_dimensions[L(2 + len(CRITS))].width = 16
v.freeze_panes = "B3"
for ws_ in (b, s, o, v):
    ws_.page_setup.orientation = "landscape"; ws_.sheet_properties.pageSetUpPr.fitToPage = True
    ws_.page_setup.fitToWidth, ws_.page_setup.fitToHeight = 1, 0
p2 = f"{OUT}/Karar_Verici_Formu.xlsx"; wb.save(p2)
print(p1, p2)
print(p1, p2)
