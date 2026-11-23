"""Aşama I: uzman içerik geçerliği (Lawshe CVR) formu. Kullanım: python build_expert_form.py [çıktı klasörü]"""
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
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from style import BODY, BOLD, TITLE, INPUT_FILL, BORDER, TOP_WRAP, header, ARIAL

EX_FONT = Font(name=ARIAL, size=10, italic=True, color="808080")
EX_FILL = PatternFill("solid", fgColor="F2F2F2")

TYPE_TR = {"benefit": "fayda", "cost": "maliyet"}
# (kod, kod, tür, ad, tanım): config.json'daki aday düzenler ve ölçütler
ITEMS = ([(a["code"], a["code"], "Alternatif", a["name"], a["definition"]) for a in CFG["alternatives"]]
         + [(c["code"], c["code"], f"Ölçüt ({TYPE_TR[c['type']]})", c["name"], c["definition"]) for c in CFG["criteria"]])
NA, NC = len(CFG["alternatives"]), len(CFG["criteria"])
CHOICES = '"Gerekli,Yararlı ama gerekli değil,Gereksiz"'


def wrap(c, font=BODY):
    c.font, c.alignment = font, TOP_WRAP
    return c


# ============================================================ 1) Uzman formu
wb = Workbook()
y = wb.active; y.title = "Yönerge"
y.column_dimensions["A"].width, y.column_dimensions["B"].width = 22, 100
rows = [
    ("Uzman görüşü formu", "YZ destekli performans değerlendirmesinde insan denetimi düzeni seçimi"),
    ("Katılımcı kodu", "[KOD]"),
    ("Uygulayan", TEAM),
    ("Amaç", f"Bir firmanın, yapay zekâ (YZ) destekli performans değerlendirmesinde hangi insan denetimi düzenini kullanacağına karar vermesini destekleyen bir karar destek sistemi kullanıyoruz. Sistemde {NA} aday düzen ve {NC} aday ölçüt var. Sizden her öğenin bu karar problemi için gerekli olup olmadığını değerlendirmenizi istiyoruz."),
    ("Nasıl doldurulur", "'Form' sayfasında yalnızca sarı hücreleri doldurun. Her satır için açılır listeden bir değerlendirme seçin, tanımın açık olup olmadığını belirtin ve isterseniz yorum yazın. Gri satır yalnızca örnektir. Formun sonunda eksik gördüğünüz alternatif ya da ölçütleri ekleyebilirsiniz."),
    ("Gerekli", "Bu öğe olmadan karar problemi eksik kalır."),
    ("Yararlı ama gerekli değil", "Öğe katkı sağlar ama çıkarılsa da karar problemi eksik kalmaz."),
    ("Gereksiz", "Öğenin bu karar problemiyle ilgisi yoktur ya da başka bir öğeyle aynı şeyi ölçer."),
    ("Alternatifler için", "'Gerekli', bu düzenin bir firmanın gerçekçi olarak seçebileceği ve diğerlerinden anlamlı biçimde ayrışan bir seçenek olduğu anlamına gelir."),
    ("Ölçütler için", "'Gerekli', düzenler arasında seçim yaparken bu ölçütün mutlaka dikkate alınması gerektiği anlamına gelir. Fayda ölçütlerinde yüksek değer, maliyet ölçütlerinde düşük değer daha iyidir."),
    ("Süre", "Yaklaşık 15–20 dakika."),
    ("Gizlilik ve analiz", PRIVACY),
]
for i, (a, b) in enumerate(rows, 1):
    wrap(y.cell(row=i, column=1, value=a), TITLE if i == 1 else BOLD)
    wrap(y.cell(row=i, column=2, value=b), BOLD if i == 1 else BODY)
    y.row_dimensions[i].height = 18 if len(b) < 100 else 15 * (len(b) // 95 + 1)

f = wb.create_sheet("Form")
for col, w in zip("ABCDEFGH", (6, 15, 7, 28, 62, 24, 13, 40)):
    f.column_dimensions[col].width = w
wrap(f.cell(row=1, column=1, value="Uzman bilgileri"), BOLD)
f.merge_cells("A1:D1")
info = [("Uzmanlık alanı", '"İnsan kaynakları yönetimi,Örgütsel davranış,YZ ve veri bilimi,İş hukuku,Veri koruma hukuku,Çalışan temsilciliği / sendika,Denetim / BT denetimi,Diğer"'),
        ("Bu alandaki deneyim (yıl)", None),
        ("Kurum türü", '"Üniversite,Özel sektör,Kamu,Sendika / meslek örgütü,Diğer"')]
for k, (lab, lst) in enumerate(info, 2):
    wrap(f.cell(row=k, column=2, value=lab))
    f.merge_cells(start_row=k, start_column=2, end_row=k, end_column=4)
    c = f.cell(row=k, column=5); c.fill, c.border, c.font = INPUT_FILL, BORDER, BODY
    if lst:
        dv = DataValidation(type="list", formula1=lst, allow_blank=True); f.add_data_validation(dv); dv.add(c.coordinate)
    else:
        dv = DataValidation(type="whole", operator="between", formula1="0", formula2="60", allow_blank=True); f.add_data_validation(dv); dv.add(c.coordinate)
H = 6
header(f, H, [("No", 6), ("Tür", 15), ("Kod", 7), ("Öğe", 28), ("Tanım", 62), ("Değerlendirme", 24), ("Tanım açık mı?", 13), ("Yorum / öneri", 40)])
ex = ["Örnek", "Ölçüt (fayda)", "–", "Kullanıcı memnuniyeti", "Çalışanların sistemden genel memnuniyeti.", "Yararlı ama gerekli değil", "Hayır", "C1 ile örtüşüyor; tanım netleşmeli."]
for j, v in enumerate(ex, 1):
    c = f.cell(row=H + 1, column=j, value=v); c.font, c.fill, c.border, c.alignment = EX_FONT, EX_FILL, BORDER, TOP_WRAP
dv1 = DataValidation(type="list", formula1=CHOICES, allow_blank=True); f.add_data_validation(dv1)
dv2 = DataValidation(type="list", formula1='"Evet,Hayır"', allow_blank=True); f.add_data_validation(dv2)
for i, (code, _, tur, ad, tanim) in enumerate(ITEMS, 1):
    r = H + 1 + i
    for j, v in enumerate((i, tur, code, ad, tanim), 1):
        c = f.cell(row=r, column=j, value=v); c.border = BORDER; wrap(c)
    for j in (6, 7, 8):
        c = f.cell(row=r, column=j); c.fill, c.border, c.font, c.alignment = INPUT_FILL, BORDER, BODY, TOP_WRAP
    dv1.add(f.cell(row=r, column=6).coordinate); dv2.add(f.cell(row=r, column=7).coordinate)
    f.row_dimensions[r].height = 15 * (len(tanim) // 58 + 1)
last = H + 1 + len(ITEMS)
r0 = last + 2
wrap(f.cell(row=r0, column=1, value="Eksik gördüğünüz alternatif ya da ölçütler"), BOLD)
header(f, r0 + 1, [("No", 6), ("Tür", 15), ("", 7), ("Öğe", 28), ("Kısa tanım", 62), ("Neden gerekli?", 24), ("", 13), ("", 40)])
dv3 = DataValidation(type="list", formula1='"Alternatif,Ölçüt"', allow_blank=True); f.add_data_validation(dv3)
for k in range(1, 4):
    r = r0 + 1 + k
    wrap(f.cell(row=r, column=1, value=k)).border = BORDER
    for j in (2, 4, 5, 6):
        c = f.cell(row=r, column=j); c.fill, c.border, c.font, c.alignment = INPUT_FILL, BORDER, BODY, TOP_WRAP
    dv3.add(f.cell(row=r, column=2).coordinate)
    f.row_dimensions[r].height = 30
f.freeze_panes = f.cell(row=H + 1, column=1)
for ws_ in (y, f):
    ws_.page_setup.orientation = "landscape"; ws_.page_setup.paperSize = ws_.PAPERSIZE_A4
    ws_.sheet_properties.pageSetUpPr.fitToPage = True; ws_.page_setup.fitToWidth = 1; ws_.page_setup.fitToHeight = 0
f.print_title_rows = f"{H}:{H}"
p1 = f"{OUT}/Uzman_IcerikGecerligi_Formu.xlsx"
wb.save(p1)
print(p1)
