"""Run: python model/run_model.py --model /path/to/finalfacialemotionmodel.keras"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import keras
from PIL import Image

parser=argparse.ArgumentParser()
parser.add_argument('--model')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
labels=['angry','happy','sad','surprise']
df=pd.read_csv(root/'data/study_manifest.csv')
x=np.stack([np.asarray(Image.open(root/i).convert('L').resize((48,48)),dtype='float32')[...,None]/255 for i in df.input])
model=keras.models.load_model(args.model or root/'model/finalfacialemotionmodel.keras')
p=model.predict(x,verbose=0)[:,[0,3,5,6]]
p/=p.sum(axis=1,keepdims=True)
df['model_prediction']=[labels[int(i)] for i in p.argmax(axis=1)]
df['model_confidence']=p.max(axis=1).round(4)
df['correct']=(df.model_prediction==df.true_label).astype(int)
df.to_csv(root/'data/study_dataset.csv',index=False)
print(df.head().to_string(index=False))
print(f'Accuracy: {df.correct.mean():.1%} ({df.correct.sum()}/{len(df)})')
