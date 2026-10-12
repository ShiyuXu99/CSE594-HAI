"""Display actual model output for one image: python model/try_model.py --image-id img_001"""
import argparse
from pathlib import Path
import numpy as np
import keras
from PIL import Image

parser=argparse.ArgumentParser()
parser.add_argument('--image-id',default='img_001')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
model=keras.models.load_model(root/'model/finalfacialemotionmodel.keras')
image=root/'data/study_images'/f'{args.image_id}.jpg'
x=np.asarray(Image.open(image).convert('L').resize((48,48)),dtype='float32')[None,...,None]/255
p=model.predict(x,verbose=0)[0,[0,3,5,6]]
p/=p.sum()
labels=['angry','happy','sad','surprise']
print('Input:',image)
print('Four-class scores:',{k:round(float(v),4) for k,v in zip(labels,p)})
print('Prediction:',labels[int(p.argmax())])
print('Confidence score:',round(float(p.max()),4))
