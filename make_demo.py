"""Re-creates the example results shown by the web page (test_data/demo_payload.json and
test_data/example_output/) from the example forms in test_data/forms.

Usage: python make_demo.py [--draws 10000]
"""
import argparse
import json
import os

from dsslib import ui

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=10000)
    a = ap.parse_args()
    out = ui.run(os.path.join(HERE, "test_data", "forms"), draws=a.draws, dirichlet=a.draws > 0,
                 out_dir=os.path.join(HERE, "test_data", "example_output"), source="demo", workers=None)
    json.dump(out, open(os.path.join(HERE, "test_data", "demo_payload.json"), "w"), ensure_ascii=False)
    print("recommended:", out.get("top"))
