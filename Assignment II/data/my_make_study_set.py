"""Reproduce the final curated selection, rather than drawing a new random set."""
from pathlib import Path
import hashlib,shutil
import pandas as pd

root=Path(__file__).resolve().parent.parent
manifest=pd.read_csv(root/'data/curated_selection_manifest.csv')
assert len(manifest)==200 and manifest.image_id.nunique()==200
assert manifest.true_label.value_counts().to_dict()=={l:50 for l in ['angry','happy','sad','surprise']}
images=root/'data/study_images';images.mkdir(exist_ok=True)
hashes=set()
for r in manifest.itertuples():
    source=root/'reference/Facial_Emotion_Recognition/images'/r.source_file
    fingerprint=hashlib.md5(source.read_bytes()).hexdigest()
    assert fingerprint not in hashes,'Duplicate image content'
    hashes.add(fingerprint)
    shutil.copyfile(source,root/r.input)
manifest.to_csv(root/'data/study_manifest.csv',index=False)
print('Recreated the fixed curated study dataset: 200 images, 50 per class.')
