"""Arayüz sayfasını üretir: şablona Python modüllerini, ayar dosyasını, örnek sonucu ve örnek formları gömer.

python web/build_page.py  ->  web/index.html
"""
import base64
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def js_json(obj):
    """<script type=application/json> içine güvenle gömülecek JSON."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


README = """DSS - bos formlar / blank forms

TR
1. Her katilimci icin ilgili formun bir kopyasini olusturun ve dosyayi kodla adlandirin:
   uzmanlar U01_Uzman_Formu.xlsx, U02_..., hukukcular H01_Hukukcu_Formu.xlsx, ...,
   karar vericiler K01_Karar_Verici_Formu.xlsx, ... Sistem rolu dosya adinin basindaki
   U, H ya da K harfinden ve numaradan tanir.
2. Her formun Yonerge sayfasindaki 'Uygulayan' ve 'Gizlilik ve analiz' satirlarini, hukukcu formunda
   ayrica 'Vaka firmasi' satirini kendi uygulamaniza gore doldurun.
3. Katilimcilar yalnizca sari hucreleri doldurur. Kontrol hucreleri eksik ya da tutarsiz yanitlari gosterir.
4. Doldurulmus dosyalarin hepsini DSS sayfasinda 'Veri ve ayarlar' bolumune yukleyin.
   Yalnizca uzman formlari yuklenirse yalniz Asama I (icerik gecerligi) calisir.

EN
1. Make one copy of the relevant form per participant and name it with a code:
   experts U01_Uzman_Formu.xlsx, lawyers H01_Hukukcu_Formu.xlsx, decision makers
   K01_Karar_Verici_Formu.xlsx, and so on. The DSS recognises each role from the letter
   and number at the start of the file name.
2. Fill in the 'Uygulayan' (who runs the study) and 'Gizlilik ve analiz' (privacy and analysis)
   rows of each form's Yonerge sheet, and the 'Vaka firmasi' (organization) row of the lawyer form.
3. Participants fill in the yellow cells only; check cells flag missing or inconsistent answers.
4. Upload all completed files under 'Data and settings'. With expert forms only, Stage I runs alone.
   The forms are in Turkish.
"""


def make_blank_zip():
    """Boş form şablonları ve kısa kullanım notu, zip olarak (base64)."""
    import io
    import zipfile
    out = os.path.join(ROOT, "forms", "blank")              # forms/build_expert_form.py ve forms/build_forms.py üretir
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for src, name in (("Uzman_IcerikGecerligi_Formu.xlsx", "U00_Uzman_Formu_BOS.xlsx"),
                          ("Hukukcu_Formu.xlsx", "H00_Hukukcu_Formu_BOS.xlsx"),
                          ("Karar_Verici_Formu.xlsx", "K00_Karar_Verici_Formu_BOS.xlsx")):
            zi = zipfile.ZipInfo("DSS_Bos_Formlar/" + name, date_time=(2026, 1, 1, 0, 0, 0))   # sabit tarih: aynı girdi, aynı sayfa
            z.writestr(zi, open(os.path.join(out, src), "rb").read(), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr(zipfile.ZipInfo("DSS_Bos_Formlar/KULLANIM_README.txt", date_time=(2026, 1, 1, 0, 0, 0)), README,
                   compress_type=zipfile.ZIP_DEFLATED)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    if not os.path.isdir(os.path.join(HERE, "pyodide_files")):
        raise SystemExit("web/pyodide_files is missing: run python web/fetch_pyodide.py first.")
    py = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "dsslib", "*.py"))):
        py["dsslib/" + os.path.basename(p)] = open(p, encoding="utf-8").read()
    py["config.json"] = open(os.path.join(ROOT, "config.json"), encoding="utf-8").read()
    demo = json.load(open(os.path.join(ROOT, "test_data", "demo_payload.json"), encoding="utf-8"))
    forms = {os.path.basename(p): base64.b64encode(open(p, "rb").read()).decode()
             for p in sorted(glob.glob(os.path.join(ROOT, "test_data", "forms", "*.xlsx")))}
    out_dir = os.path.join(ROOT, "test_data", "example_output")
    xl = dict(xlsx=base64.b64encode(open(os.path.join(out_dir, "DSS_Rapor.xlsx"), "rb").read()).decode(),
              json=open(os.path.join(out_dir, "DSS_Ozet.json"), encoding="utf-8").read())
    blank = make_blank_zip()
    wheels = {os.path.basename(p): base64.b64encode(open(p, "rb").read()).decode()
              for p in sorted(glob.glob(os.path.join(HERE, "wheels", "*.whl")))}
    html = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    for key, val in (("__PY_FILES__", py), ("__DEMO_PAYLOAD__", demo), ("__DEMO_FORMS__", forms), ("__DEMO_XLSX__", xl),
                     ("__WHEELS__", wheels), ("__BLANK_ZIP__", blank)):
        assert html.count(key) == 1, key
        html = html.replace(key, js_json(val))
    out = os.path.join(HERE, "index.html")
    open(out, "w", encoding="utf-8").write(html)
    # yayın klasörü: sayfa, worker ve Pyodide dosyaları (CDN'e fetch engelli olduğu için sayfanın kendi dosyaları)
    import shutil
    dist = os.path.join(HERE, "dist")
    shutil.rmtree(dist, ignore_errors=True)
    os.makedirs(os.path.join(dist, "pyodide"))
    shutil.copy(out, os.path.join(dist, "index.html"))
    shutil.copy(os.path.join(HERE, "worker.js"), os.path.join(dist, "worker.js"))
    for f in os.listdir(os.path.join(HERE, "pyodide_files")):
        src = os.path.join(HERE, "pyodide_files", f)
        if f.endswith((".zip", ".whl")):      # sunucu bu uzantıları sunmuyor: base64 metin
            open(os.path.join(dist, "pyodide", f + ".b64.txt"), "w").write(base64.b64encode(open(src, "rb").read()).decode())
        else:
            shutil.copy(src, os.path.join(dist, "pyodide", f))
    print(out, f"{len(html) / 1024:.0f} KB", len(forms), "örnek form")


if __name__ == "__main__":
    main()
