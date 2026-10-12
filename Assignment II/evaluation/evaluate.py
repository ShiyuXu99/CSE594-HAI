from pathlib import Path
import json
import pandas as pd
from sklearn.metrics import classification_report,confusion_matrix

root=Path(__file__).resolve().parent.parent
df=pd.read_csv(root/'data/study_dataset.csv')
labels=['angry','happy','sad','surprise']
correct=(df.true_label==df.model_prediction)
assert (correct.astype(int)==df.correct).all()
assert len(df)==200 and df.image_id.nunique()==200
print(f'Accuracy: {correct.mean():.1%} ({correct.sum()}/{len(df)})')
print(df.true_label.value_counts().to_string())
print(classification_report(df.true_label,df.model_prediction,labels=labels,digits=3))
print(pd.DataFrame(confusion_matrix(df.true_label,df.model_prediction,labels=labels),index=labels,columns=labels))
cm=pd.DataFrame(confusion_matrix(df.true_label,df.model_prediction,labels=labels),index=['true_'+l for l in labels],columns=['pred_'+l for l in labels])
cm.to_csv(root/'evaluation/confusion_matrix_study.csv')
df['conf_bin']=pd.cut(df.model_confidence,bins=[0,0.5,0.7,0.9,1.0001],right=False)
df[~correct].sort_values('model_confidence',ascending=False).to_csv(root/'evaluation/model_errors.csv',index=False)
print(df.groupby('conf_bin',observed=True).correct.agg(['count','mean']))
metrics={'n':len(df),'correct':int(correct.sum()),'errors':int((~correct).sum()),'accuracy':float(correct.mean()),'classification_report':classification_report(df.true_label,df.model_prediction,labels=labels,output_dict=True)}
(root/'evaluation/evaluation.json').write_text(json.dumps(metrics,indent=2))

import runpy
runpy.run_path(str(root / "evaluation/analyze_confidence.py"), run_name="__main__")
