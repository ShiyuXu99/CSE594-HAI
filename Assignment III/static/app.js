const condition=document.body.dataset.condition;
const $=s=>document.querySelector(s);
const labels=[['angry','Angry','Tense or lowered brows, pressed lips, or a scowl.'],['happy','Happy','A smile, raised cheeks, or a joyful expression.'],['sad','Sad','Downturned mouth, raised inner brows, or a sorrowful expression.'],['surprise','Surprise','Raised brows, widened eyes, or an open mouth.']];
let study=null,busy=false,activeMs=0,visibleSince=null,imageReady=false,aiReady=condition!=='ai',inferenceId=null,renderVersion=0,predicting=false;
const title=label=>labels.find(x=>x[0]===label)?.[1]||label;
for(const [value,name,description] of labels){
 for(const [container,group] of [['#emotion-options','label'],['#check-options','check']]){
  const label=document.createElement('label');label.className='emotion-option';
  const input=document.createElement('input');input.type='radio';input.name=group;input.value=value;input.required=true;
  label.append(input,document.createTextNode(name));$(container).append(label);
 }
 const p=document.createElement('p'),strong=document.createElement('strong');strong.textContent=name+': ';p.append(strong,document.createTextNode(description));$('#emotion-guide').append(p);
}
function pauseTimer(){if(visibleSince!==null){activeMs+=performance.now()-visibleSince;visibleSince=null;}}
function resumeTimer(){if(imageReady&&!document.hidden&&visibleSince===null)visibleSince=performance.now();}
document.addEventListener('visibilitychange',()=>document.hidden?pauseTimer():resumeTimer());
function error(message){$('#error').textContent=message;$('#error').hidden=false;}
async function requestApi(action,body){
 const response=await fetch(`/api/${condition}/${action}`,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':$('meta[name="csrf-token"]').content},...(body===undefined?{}:{body:JSON.stringify(body)})});
 let data;try{data=await response.json();}catch{throw Error('The server did not respond. Please retry.');}
 if(!response.ok)throw Error(data.error||'Unable to save. Please retry.');return data;
}
async function api(action,body){$('#error').hidden=true;return (await requestApi(action,body)).study;}
function controls(){
 const selected=$('input[name="label"]:checked');
 $('#trial-confidence').hidden=!selected;
 $('#trial-confidence').disabled=!selected||busy||!imageReady;
 $('#answers').disabled=busy||!imageReady;
 $('#next').disabled=busy||!imageReady||!aiReady||!selected||!$('input[name="trial_confidence"]:checked');
}
async function loadAI(version){
 if(predicting||version!==renderVersion||!study?.trial)return;
 predicting=true;aiReady=false;inferenceId=null;controls();$('#ai-status').hidden=false;$('#ai-status').textContent='Analyzing…';$('#ai-result').hidden=true;$('#ai-retry').hidden=true;
 const trial=study.trial,body={session_id:study.session_id,image_id:trial.image_id};
 try{
  const {output}=await requestApi('predict',body);
  if(version!==renderVersion)return;
  $('#ai-label').textContent=title(output.prediction);
  const percent=Math.round(output.confidence*100);$('#ai-confidence').textContent=`${percent}%`;$('#ai-meter').value=output.confidence;
  $('#ai-result').hidden=false;$('#ai-status').hidden=true;
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  if(version!==renderVersion)return;
  await requestApi('displayed',{...body,inference_id:output.inference_id});
  if(version!==renderVersion)return;
  inferenceId=output.inference_id;aiReady=true;
 }catch(e){if(version===renderVersion){$('#ai-status').hidden=false;$('#ai-status').textContent=e.message;$('#ai-retry').hidden=false;}}
 finally{predicting=false;if(version===renderVersion)controls();}
}
function render(){
 const version=++renderVersion;pauseTimer();imageReady=false;aiReady=condition!=='ai';inferenceId=null;$('#loading').hidden=true;
 for(const id of ['intro','attention','task','survey','complete'])$('#'+id).hidden=true;
 if(!study){$('#intro').hidden=false;return;}
 if(study.completed){$('#complete').hidden=false;$('#completed-id').textContent=study.participant_id;return;}
 if(study.attention_due){$('#attention').hidden=false;$('#attention-form').reset();activeMs=0;imageReady=true;resumeTimer();return;}
 if(!study.trial){
  $('#survey').hidden=false;const scale=study.rating_scale||5;
  for(const name of ['workload','confidence']){
   const options=$('#'+name+' .rating-options');options.replaceChildren();options.style.setProperty('--rating-count',scale);
   for(let n=1;n<=scale;n++){
    const label=document.createElement('label');label.className='rating-option';
    const input=document.createElement('input');input.type='radio';input.name=name;input.value=String(n);input.required=true;
    const score=document.createElement('span');score.textContent=String(n);label.append(input,score);options.append(label);
   }
   const anchors=$('#'+name+'-anchors');
   anchors.firstElementChild.textContent=name==='workload'?'1 · Very low':'1 · Not at all confident';
   anchors.lastElementChild.textContent=name==='workload'?`${scale} · Very high`:`${scale} · Extremely confident`;
  }
  return;
 }
 $('#task').hidden=false;$('#participant-id').textContent=study.participant_id;
 $('#progress-text').textContent=`Image ${study.trial.position} of ${study.total}`;$('#progress').value=study.answered;
 $('#answer-form').reset();$('#trial-confidence').hidden=true;$('#trial-confidence').disabled=true;$('#answers').disabled=true;$('#next').disabled=true;
 $('#next').textContent=study.trial.position===study.total?'Save & continue':'Save & next';$('#ai-panel').hidden=condition!=='ai';
 activeMs=0;const img=$('#study-image');
 img.onload=()=>{if(version!==renderVersion)return;imageReady=true;controls();resumeTimer();if(condition==='ai')loadAI(version);};
 img.onerror=()=>error('This image could not load. Refresh to retry; your saved progress is kept.');
 img.src=study.trial.image_url;
 if(condition==='ai'){$('#ai-status').hidden=false;$('#ai-status').textContent='Loading image…';$('#ai-result').hidden=true;$('#ai-retry').hidden=true;}
}
async function run(button,fn){if(busy)return;busy=true;button.disabled=true;try{study=await fn();render();}catch(e){error(e.message);}finally{busy=false;button.disabled=false;if(study?.trial&&!study.attention_due)controls();}}
$('#start-form').onsubmit=e=>{e.preventDefault();run($('#start'),()=>api('start',{user_name:$('#user-name').value.trim()}));};
$('#attention-form').onsubmit=e=>{e.preventDefault();const selected=$('input[name="check"]:checked');if(selected&&!busy){pauseTimer();run(e.submitter,()=>api('attention',{answer:selected.value,active_ms:Math.round(activeMs)})).then(resumeTimer);}};
$('#answer-form').onchange=controls;
$('#answer-form').onsubmit=e=>{e.preventDefault();const selected=$('input[name="label"]:checked');if(!selected||!imageReady||!aiReady||busy)return;pauseTimer();run($('#next'),()=>api('answer',{session_id:study.session_id,image_id:study.trial.image_id,label:selected.value,trial_confidence:Number($('input[name="trial_confidence"]:checked')?.value),active_ms:Math.round(activeMs),...(condition==='ai'?{inference_id:inferenceId}:{})})).then(resumeTimer);};
$('#survey-form').onsubmit=e=>{e.preventDefault();run(e.submitter,()=>api('finish',{workload:Number($('input[name="workload"]:checked')?.value),confidence:Number($('input[name="confidence"]:checked')?.value),comments:$('#comments').value}));};
$('#guide-button').onclick=()=>$('#guide').showModal();$('#close-guide').onclick=()=>$('#guide').close();
$('#ai-retry').onclick=()=>loadAI(renderVersion);
$('#retest-button')?.addEventListener('click',()=>{if(busy||predicting)return;if(study?.user_name)$('#user-name').value=study.user_name;run($('#retest-button'),()=>api('retest',{}));});
(async()=>{try{study=await api('state');render();}catch(e){$('#loading').textContent='Unable to load the study. Refresh to retry.';error(e.message);}})();
