# How to Run

Folders: `data/` contains the study images and dataset; `model/` contains the
model and inference scripts; `evaluation/` contains evaluation scripts and
results. The original repository is under `reference/`.

From the A2_Code folder, activate the existing environment:

```bash
source .venv/bin/activate
```

On another machine, create an environment first:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run in order:

```bash
python model/run_model.py
python evaluation/evaluate.py
python evaluation/error_table.py
python evaluation/make_montage.py
```

Expected result: 68.0% accuracy (136/200), with 64 errors. The evaluation step also prints confidence analysis and saves confidence tables and metrics in `evaluation/`.

To run only the confidence analysis:

```bash
python evaluation/analyze_confidence.py
```

Display a single prediction:

```bash
python model/try_model.py --image-id img_001
```

The final images are included. Optionally rebuild the same images before
inference (requires the original images/test folder under reference/):

```bash
python data/my_make_study_set.py
```
