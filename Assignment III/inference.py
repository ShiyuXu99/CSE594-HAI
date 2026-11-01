"""Real-time CPU inference with Assignment II weights, exported without retraining."""
import hashlib
import threading
import time
from pathlib import Path
import numpy as np
from PIL import Image
import onnxruntime as ort
LABELS=('angry','happy','sad','surprise')
MODEL_PATH=Path(__file__).resolve().parent/'model/emotion.onnx'
_session=None
_lock=threading.Lock()
_version=None

def warmup():
    global _session,_version
    if _session is None:
        with _lock:
            if _session is None:
                options=ort.SessionOptions()
                options.intra_op_num_threads=1
                options.inter_op_num_threads=1
                candidate=ort.InferenceSession(str(MODEL_PATH),sess_options=options,providers=['CPUExecutionProvider'])
                candidate.run(None,{candidate.get_inputs()[0].name:np.zeros((1,48,48,1),dtype=np.float32)})
                _version='a2-onnx-'+hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()[:16]
                _session=candidate
    return _session

def predict_image(path):
    started=time.perf_counter()
    model=warmup()
    with Image.open(path) as image:
        image=np.asarray(image.convert('L').resize((48,48)),dtype=np.float32)[None,...,None]/255
    scores=model.run(None,{model.get_inputs()[0].name:image})[0][0,[0,3,5,6]]
    if not np.isfinite(scores).all() or scores.sum()<=0: raise ValueError('Invalid model output')
    scores=scores/scores.sum()
    return {'prediction':LABELS[int(scores.argmax())],'confidence':float(scores.max()),
            'scores':{label:float(value) for label,value in zip(LABELS,scores)},
            'model_version':_version,'latency_ms':round((time.perf_counter()-started)*1000,3)}
