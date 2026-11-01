"""Optional model rebuild. Requires tensorflow==2.20.0, tf2onnx, onnx and deployment dependencies."""
import os,sys,time,json,hashlib,csv,statistics
os.environ['TF_CPP_MIN_LOG_LEVEL']='3';os.environ['KERAS_HOME']='/tmp/hai-keras'

from pathlib import Path
import numpy as np,keras,tensorflow as tf
from PIL import Image
root=Path(__file__).resolve().parents[2]/'Assignment II'
model=keras.models.load_model(root/'model/finalfacialemotionmodel.keras',compile=False)
model.export(str(Path(__file__).resolve().parents[1]/'model/emotion.onnx'),format='onnx',verbose=False,input_signature=[tf.TensorSpec((None,48,48,1),tf.float32,name='image')])
import onnxruntime as ort
opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
session=ort.InferenceSession(str(Path(__file__).resolve().parents[1]/'model/emotion.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
rows=list(csv.DictReader((root/'data/study_dataset.csv').open()));times=[];matches=0;maxdiff=0
for row in rows:
 x=np.asarray(Image.open(root/row['input']).convert('L').resize((48,48)),dtype='float32')[None,...,None]/255
 start=time.perf_counter();out=session.run(None,{session.get_inputs()[0].name:x})[0][0,[0,3,5,6]];out/=out.sum();times.append(time.perf_counter()-start)
 label=['angry','happy','sad','surprise'][int(out.argmax())];matches+=label==row['model_prediction'];maxdiff=max(maxdiff,abs(float(out.max())-float(row['model_confidence'])))
assert matches==200 and maxdiff<0.0002,(matches,maxdiff)
result={'source_sha256':hashlib.sha256((root/'model/finalfacialemotionmodel.keras').read_bytes()).hexdigest(),'onnx_sha256':hashlib.sha256((Path(__file__).resolve().parents[1]/'model/emotion.onnx').read_bytes()).hexdigest(),'label_matches':matches,'max_difference_from_rounded_stored_confidence':maxdiff,'median_inference_ms':statistics.median(times)*1000,'onnx_size_mb':(Path(__file__).resolve().parents[1]/'model/emotion.onnx').stat().st_size/1024**2,'preprocessing':'Pillow grayscale, 48x48 default resize, float32 /255, indices 0,3,5,6 renormalized','labels':['angry','happy','sad','surprise']}
(Path(__file__).resolve().parents[1]/'model/validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
