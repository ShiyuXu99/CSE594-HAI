from pathlib import Path
import pandas as pd
from PIL import Image,ImageDraw

root=Path(__file__).resolve().parent.parent
errors=pd.read_csv(root/'evaluation/model_errors.csv')
cols,size,caption=6,150,40
canvas=Image.new('RGB',(cols*size,((len(errors)+cols-1)//cols)*(size+caption)),'white')
draw=ImageDraw.Draw(canvas)
for k,r in enumerate(errors.itertuples()):
    x,y=k%cols*size,k//cols*(size+caption)
    canvas.paste(Image.open(root/r.input).convert('RGB').resize((size,size)),(x,y))
    draw.text((x+2,y+size+2),f'{r.image_id} T:{r.true_label}',fill='black')
    draw.text((x+2,y+size+17),f'AI:{r.model_prediction} {r.model_confidence:.2f}',fill='red')
canvas.save(root/'evaluation/figures/error_montage.png')
print(f'Saved montage of {len(errors)} errors.')
