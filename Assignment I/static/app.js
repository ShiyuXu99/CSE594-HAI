const emotions = [
  {name: 'anger', emoji: '😠', description: 'Frustration, irritation, or hostility'},
  {name: 'fear', emoji: '😨', description: 'Worry, anxiety, or feeling threatened'},
  {name: 'joy', emoji: '😄', description: 'Happiness, delight, or satisfaction'},
  {name: 'love', emoji: '🥰', description: 'Affection, care, or tenderness'},
  {name: 'sadness', emoji: '😢', description: 'Sorrow, disappointment, or loss'},
  {name: 'surprise', emoji: '😲', description: 'Amazement or an unexpected feeling'},
];
const $ = (selector) => document.querySelector(selector);
let task = null;
let busy = false;
let enteredTask = false;
const csrfToken = $('meta[name="csrf-token"]').content;
for (const emotion of emotions) {
  const title = emotion.name[0].toUpperCase() + emotion.name.slice(1);
$('#emotion-guide').insertAdjacentHTML('beforeend', `<div class="intro-emotion-item"><span class="intro-emotion-emoji" aria-hidden="true">${emotion.emoji}</span><span class="intro-emotion-text"><strong>${title}.</strong> ${emotion.description}</span></div>`);
  $('#emotion-options').insertAdjacentHTML('beforeend', `<label class="emotion-option"><input type="radio" name="emotion" value="${emotion.name}"><span class="emotion-emoji" aria-hidden="true">${emotion.emoji}</span><span>${title}</span><div class="definition"><button type="button" class="help-button" aria-label="What does ${title.toLowerCase()} mean?" aria-describedby="definition-${emotion.name}">?</button><span class="tooltip" role="tooltip" id="definition-${emotion.name}">${emotion.description}.</span></div></label>`);
}
document.querySelectorAll('.definition').forEach(definition => {
  const button = definition.querySelector('button');
  button.addEventListener('click', () => definition.classList.toggle('open'));
  button.addEventListener('focus', () => definition.classList.remove('dismissed'));
  definition.addEventListener('mouseenter', () => definition.classList.remove('dismissed'));
  button.addEventListener('blur', () => definition.classList.remove('open'));
  definition.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      definition.classList.remove('open');
      definition.classList.add('dismissed');
    }
  });
});
function showError(message) { $('#error').textContent = message; $('#error').hidden = false; }
async function api(path, body) {
  $('#error').hidden = true;
  const response = await fetch(path, {method: body ? 'POST' : 'GET', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken}, ...(body ? {body: JSON.stringify(body)} : {})});
  let data;
  try { data = await response.json(); } catch { throw new Error('The server could not respond. Please try again.'); }
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data.task;
}
function render(focus = false) {
  $('#loading').hidden = true;
  $('#intro').hidden = enteredTask || Boolean(task?.completed);
  $('#start-button').textContent = task ? 'Continue labeling' : 'Start labeling';
  $('#task').hidden = !enteredTask || !task || task.completed;
  $('#complete').hidden = !task || !task.completed;
  if (!task) return;
  $('#participant-id').textContent = task.participant_id;
  if (task.completed) { $('#completed-id').textContent = task.participant_id; if (focus) $('#complete').scrollIntoView({behavior:'smooth'}); return; }
  const current = task.tweets.find(tweet => !tweet.selected_label);
  if (!current) { showError('Please refresh to check your completion status.'); return; }
  $('#progress-text').textContent = `Tweet ${current.position} of 5`;
  $('#progress').value = task.tweets.filter(tweet => tweet.selected_label).length;
  $('#tweet-text').textContent = current.text;
  $('#answer-form').reset();
  $('#next-button').innerHTML = current.position === 5 ? 'Save & finish' : 'Save & next';
  $('#next-button').disabled = true;
  if (focus) $('#tweet-text').focus();
}
const tutorialDialog = $('#tutorial-dialog');
$('#open-tutorial').addEventListener('click', () => tutorialDialog.showModal());
$('#open-tutorial-hint').addEventListener('click', () => tutorialDialog.showModal());
$('#close-tutorial').addEventListener('click', () => tutorialDialog.close());
tutorialDialog.addEventListener('click', event => {
  const bounds = tutorialDialog.getBoundingClientRect();
  if (event.target === tutorialDialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) tutorialDialog.close();
});
$('#emotion-options').addEventListener('change', () => { $('#next-button').disabled = busy; });
$('#start-button').addEventListener('click', async () => {
  if (busy) return;
  busy = true; $('#start-button').disabled = true; $('#start-button').textContent = 'Preparing your tweets…';
  try { task = await api('/api/start', {}); enteredTask = true; render(true); } catch (error) { showError(error.message); }
  finally { busy = false; $('#start-button').disabled = false; $('#start-button').textContent = task ? 'Continue labeling' : 'Start labeling'; }
});
$('#answer-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const selected = $('input[name="emotion"]:checked');
  if (busy || !selected) return;
  busy = true; $('#next-button').disabled = true; $('#emotion-options').closest('fieldset').disabled = true;
  const previousText = $('#next-button').innerHTML;
  $('#next-button').textContent = 'Saving…';
  try {
    const current = task.tweets.find(tweet => !tweet.selected_label);
    task = await api('/api/answer', {task_id: task.task_id, tweet_id: current.tweet_id, label: selected.value});
    render(true);
  } catch (error) { showError(error.message); $('#next-button').innerHTML = previousText; $('#next-button').disabled = false; }
  finally { busy = false; $('#emotion-options').closest('fieldset').disabled = false; }
});
(async () => {
  try { task = await api('/api/task'); render(); }
  catch (error) { $('#loading').textContent = 'Unable to load your task. Refresh to retry.'; showError(error.message); }
})();

$('#again-button').addEventListener('click', async () => {
  if (busy) return;
  busy = true; $('#again-button').disabled = true; $('#again-button').textContent = 'Preparing your tweets…';
  try { task = await api('/api/start', {previous_task_id: task.task_id}); enteredTask = true; render(true); } catch (error) { showError(error.message); }
  finally { busy = false; $('#again-button').disabled = false; $('#again-button').textContent = 'Label more tweets'; }
});
