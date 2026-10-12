# Assignment II — How to Run

Use Python 3.12. From the repository root, enter the assignment folder and
set up an environment:

```bash
cd "Assignment II"
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

Expected result: 68.0% accuracy (136/200), with 64 errors. Evaluation also
calculates confidence calibration and saves its tables and metrics.

To display one model prediction:

```bash
python model/try_model.py --image-id img_001
```

To run only the confidence analysis:

```bash
python evaluation/analyze_confidence.py
```

## Files

- `data/study_dataset.csv`: 200 trials with input paths, labels, predictions,
  confidence scores, and correctness.
- `data/study_images/`: the 200 input images.
- `model/`: the pretrained model and inference scripts.
- `evaluation/`: evaluation scripts, metrics, error tags, and distribution table.
- `evaluation/figures/error_montage.png`: the error image montage.

The study images are already included; no resampling is needed. Optional
rebuilding uses the fixed selection in `data/curated_selection_manifest.csv`:

```bash
python data/my_make_study_set.py
```

This optional command requires the original repository and its `images/test`
folder at `reference/Facial_Emotion_Recognition`. That reference folder is
excluded from this GitHub repository and is not needed for the normal run.

Original model repository:
https://github.com/lokeshkumar80/Facial_Emotion_Recognition
