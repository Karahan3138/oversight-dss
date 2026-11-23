"use strict";
const BASE = new URL("pyodide/", self.location.href).href;
// Yayın sunucusu .zip/.whl dosyalarını sunmadığı için bu dosyalar base64 metin (.b64.txt) olarak duruyor.
// Pyodide'nin isteklerini bu metinlere yönlendirip baytlara çeviriyoruz (aynı köken, ek izin gerekmez).
const PACKED = ["python_stdlib.zip", "numpy-1.26.4-cp312-cp312-pyodide_2024_0_wasm32.whl",
  "scipy-1.12.0-cp312-cp312-pyodide_2024_0_wasm32.whl", "openblas-0.3.26.zip",
  "clarabel-0.7.1-cp37-abi3-pyodide_2024_0_wasm32.whl"];
const nativeFetch = self.fetch.bind(self);
function b64bytes(b64) {
  if (Uint8Array.fromBase64) return Uint8Array.fromBase64(b64.trim());
  const bin = atob(b64.trim()); const u = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  return u;
}
self.fetch = async (input, init) => {
  const url = typeof input === "string" ? input : (input && input.url) || String(input);
  const name = PACKED.find((n) => url.split("?")[0].endsWith("/" + n));
  if (name) {
    const r = await nativeFetch(BASE + name + ".b64.txt");
    if (!r.ok) return r;
    const bytes = b64bytes(await r.text());
    return new Response(bytes, { status: 200, headers: { "Content-Type": "application/octet-stream" } });
  }
  return nativeFetch(input, init);
};
const diag = (t) => postMessage({ type: "diag", text: t });
self.addEventListener("error", (e) => diag("worker error: " + e.message));
self.addEventListener("unhandledrejection", (e) => diag("unhandled: " + (e.reason && (e.reason.message || e.reason))));
try { importScripts(BASE + "pyodide.js"); diag("pyodide.js: ok"); } catch (e) { diag("pyodide.js: " + e); throw e; }
let py = null;
async function probe(name) {
  try { const r = await fetch(BASE + name); return name + ": HTTP " + r.status; } catch (e) { return name + ": " + e; }
}
async function boot(files, wheels) {
  try { new WebAssembly.Module(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0])); diag("WebAssembly: ok"); }
  catch (e) { diag("WebAssembly: " + e); }
  diag(await probe("pyodide-lock.json"));
  diag(await probe("pyodide.asm.wasm"));
  diag(await probe("python_stdlib.zip.b64.txt"));
  py = await loadPyodide({ indexURL: BASE, stdout: () => {}, stderr: (t) => diag("stderr: " + t) });
  diag("loadPyodide: ok");
  postMessage({ type: "status", key: "pkgs" });
  await py.loadPackage(["numpy", "scipy", "clarabel"]);
  py.FS.mkdirTree("/app/wheels");
  for (const [name, b64] of Object.entries(wheels)) {
    const bin = atob(b64); const u = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    py.FS.writeFile("/app/wheels/" + name, u);
  }
  py.runPython("import zipfile, glob, sys\nfor w in glob.glob('/app/wheels/*.whl'):\n    zipfile.ZipFile(w).extractall('/app/site')\nsys.path.insert(0, '/app/site')");
  for (const [path, src] of Object.entries(files)) {
    const dir = "/app/" + path.split("/").slice(0, -1).join("/");
    py.FS.mkdirTree(dir); py.FS.writeFile("/app/" + path, src);
  }
  py.runPython("import sys; sys.path.insert(0, '/app')");
  py.setStdout({ batched: (s) => { if (s.startsWith("PROGRESS")) postMessage({ type: "progress", text: s }); } });
  postMessage({ type: "status", key: "ready" });
}
onmessage = async (e) => {
  const m = e.data;
  try {
    if (m.type === "boot") await boot(m.files, m.wheels);
    if (m.type === "run") {
      py.runPython("import shutil, os; shutil.rmtree('/data', ignore_errors=True); os.makedirs('/data/forms')");
      for (const f of m.files) py.FS.writeFile("/data/forms/" + f.name, new Uint8Array(f.buf));
      py.globals.set("params_json", JSON.stringify(m.params));
      const code = "from dsslib import ui\nui.run_json('/data/forms', params_json, " + (m.draws > 0 ? m.draws : "None") + ", " + (m.draws > 0 ? "True" : "False") + ", '/data/out', '" + m.source + "')";
      const res = py.runPython(code);
      let xlsx = null, js = null;
      try { xlsx = py.FS.readFile("/data/out/DSS_Rapor.xlsx"); js = py.FS.readFile("/data/out/DSS_Ozet.json"); } catch (_) {}
      postMessage({ type: "result", json: res, xlsx, js });
    }
  } catch (err) { postMessage({ type: "error", text: String(err && err.message || err) }); }
};