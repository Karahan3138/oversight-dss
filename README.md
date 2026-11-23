# Oversight Arrangement DSS

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24451451.svg)](https://doi.org/10.5281/zenodo.24451451)

A case-based decision support system (DSS) that helps an organization choose a human oversight arrangement for AI-supported performance appraisal. It combines

- content validation of the candidate arrangements and criteria (Lawshe's content validity ratio with exact critical values),
- a neutrosophic legal admissibility screening based on lawyers' degrees of satisfaction, indeterminacy and violation,
- two-level best–worst method (BWM) weights and single-valued neutrosophic (SVN) performance ratings,
- a minimum-cost consensus model that caps the consensus burden of the least powerful stakeholder group, with voice measures for that group, and
- validation against six ranking methods, other treatments of the legal requirements and sensitivity analyses.

The method is described in the accompanying article [citation to be added]. Equation numbers in the code (`Eş.`/`Eq.`) refer to that article.

**Run it in the browser:** [https://karahan3138.github.io/oversight-dss/](https://karahan3138.github.io/oversight-dss/) (no installation; the Python code runs in the browser and the forms never leave your computer).

**Archived version:** v1.0.0, [https://doi.org/10.5281/zenodo.24451451](https://doi.org/10.5281/zenodo.24451451)

## Use

### In the browser

1. Open the page and choose *Data and settings*.
2. Download the blank forms, make one copy per participant and name the files with a code: `U01_…` for experts, `H01_…` for lawyers and `K01_…` for decision makers.
3. Load the completed forms, set the parameters if needed and run the analysis. The results can be downloaded as an Excel report and a JSON summary.

The page opens with the results of the synthetic example forms in `test_data/forms`. The interface is in English and Turkish; the forms are in Turkish.

### From Python

Tested with Python 3.12 (NumPy 1.26.4, SciPy 1.12.0) and Python 3.13 (NumPy 2.5, SciPy 1.18), with openpyxl 3.1.5 and Clarabel 0.7.1.

```
pip install -r requirements.txt
python run_case.py --forms test_data/forms --out results            # full analysis, 10,000 Dirichlet draws
python run_case.py --forms test_data/forms --out results --draws 2000
python run_case.py --forms test_data/forms --out results --no-dirichlet
python -m pytest -q tests
```

If the folder contains only expert forms, only Stage I (content validity) runs. The Dirichlet draws are split into blocks with seeds of their own, so the results do not depend on the number of processor cores.

## Adapting the DSS

`config.json` is the single source for the library of arrangements and criteria, the dimensions, the legal requirements, the scales, the mapping from organizational level to power and all parameters. After editing it, rebuild the forms and the page:

```
python forms/build_expert_form.py      # Stage I form  -> forms/blank/
python forms/build_forms.py            # Stage II and III forms -> forms/blank/
python web/fetch_pyodide.py            # once: Pyodide 0.26.4 runtime -> web/pyodide_files/
python web/build_page.py               # -> web/dist/ (copy to docs/ to publish with GitHub Pages)
```

The `forms` block of `config.json` sets the text that each form shows about who runs the study and how the answers are handled. Fill it in, and the "Vaka firması" (organization) row of the lawyer form, before sending the forms.

## Reproducing the article

| Article | Code |
|---|---|
| Method, Eqs. (1)–(34) | `dsslib/engine.py` (Stages I–IV), `dsslib/pipeline.py` (Stage V) |
| Benchmark methods, Eqs. (B.1)–(B.14) | `dsslib/benchmarks.py` |
| Synthetic evaluation (Section 5, Tables 4–5) | `python synthetic.py` → `test_data/synthetic_results.json` (about 8 min on two cores) |
| Example forms and the results shown by the page | `python make_test_data.py`, `python make_demo.py` |

`tests/test_engine.py` checks the engine against published worked examples (critical values of Ayre & Scally, 2014; Example 1 of Liang et al., 2020; the CoCoSo example of Yazdani et al., 2019; the MABAC example of Pamučar & Ćirović, 2015), against hand calculations, against a second, dense formulation of the consensus linear programs, and checks that the consensus solutions are unique.

## Implementation rules not stated in the article

1. The percentile that sets γ uses linear interpolation (NumPy default, Hyndman–Fan type 7).
2. In the second problem of M0 and in the cap of M2, the right-hand side gets a relative slack of 10⁻⁹ (plus 10⁻¹⁰ absolute) for numerical feasibility.
3. The second stage of Eq. (21) keeps the linear-programming optimum within a relative tolerance of 10⁻⁷ (plus 10⁻⁹ absolute). If Clarabel is not available or fails, the first optimal solution of the linear program is used and a warning is written.
4. If T_i + I_i + F_i = 0, the compliance value is θ and a warning is written.
5. In CoCoSo, if the smallest S or P is zero, the denominator of σ_ib is the smallest positive value.
6. Zero weights in the Dirichlet parameters are raised to 10⁻⁶; γ is recomputed with Eq. (16) in each draw.
7. With tied group scores, the first arrangement in order is chosen and the tie is reported.
8. If a form gives different values of a_BW in its two rows, Eq. (8) uses both values as given, Eq. (9) uses the first, and a warning is written.
9. A decision maker with a missing comparison set or rating is left out of the analysis and reported.

## Repository layout

```
config.json              library, scales and parameters
dsslib/                  engine (Stages I–V), form reader, report, web interface bridge
run_case.py              command line
forms/                   form builders and blank forms (Turkish)
test_data/               synthetic example forms, example results, synthetic evaluation results
synthetic.py             synthetic evaluation of the article
make_test_data.py        generates the example forms
make_demo.py             generates the example results shown by the page
tests/                   automated tests
web/                     page template, Web Worker, build and Pyodide download scripts
docs/                    built page, published with GitHub Pages
```

Code comments are partly in Turkish.

## License and citation

MIT License (see `LICENSE`). If you use the DSS, please cite the article and this software:

Kara, K., Yıkılmaz, İ., & Yalçın, G. C. (2026). *Oversight Arrangement DSS: A decision support system for choosing human oversight of AI-supported performance appraisal* (Version 1.0.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24451451
