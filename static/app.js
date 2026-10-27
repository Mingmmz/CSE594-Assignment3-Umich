'use strict';
const $ = id => document.getElementById(id);
const condition = $('main').dataset.condition;
const storageKey = `pi-a3-${condition}`;
let token = null, currentState = null, busy = false, renderVersion = 0;
let originalURL = null, camURL = null, assetError = null;
let imageReady = false, camReady = false;
function read(key) { try { return localStorage.getItem(key); } catch { return null; } }
function write(key, value) { try { localStorage.setItem(key, value); } catch { /* In-memory run still works. */ } }
function remove(key) { try { localStorage.removeItem(key); } catch { /* No stored state. */ } }
function showError(message) { $('global-error').textContent = message; $('global-error').hidden = false; }
function clearError() { $('global-error').hidden = true; }
async function api(path, body) {
  const headers = { 'X-Session-Token': token || '' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(path, { method: body === undefined ? 'GET' : 'POST', headers,
    body: body === undefined ? undefined : JSON.stringify(body), cache: 'no-store' });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Connection interrupted. Please retry; saved answers are preserved.');
  return data;
}
async function perform(action) {
  if (busy) return;
  busy = true; clearError();
  document.body.setAttribute('aria-busy', 'true');
  try { await action(); }
  catch (error) { showError(error.message || 'Unable to connect. Please try again.'); }
  finally { busy = false; document.body.removeAttribute('aria-busy'); updateAnswerButton(); }
}
function showSection(name) {
  for (const id of ['welcome','attention','trial-workspace','survey','complete','recovery']) $(id).hidden = id !== name;
}
function labelName(value) { return value === 'fake' ? 'Counterfeit' : 'Genuine'; }
function updateAnswerButton() {
  const review = currentState?.current?.status === 'review';
  $('answer-button').disabled = busy || !imageReady || (review && condition === 'ai' && !camReady) || Boolean(assetError);
}
function releaseImages() {
  if (originalURL) URL.revokeObjectURL(originalURL);
  if (camURL) URL.revokeObjectURL(camURL);
  originalURL = camURL = null;
}
async function loadBlob(path) {
  const res = await fetch(path, { headers: { 'X-Session-Token': token }, cache: 'no-store' });
  if (!res.ok) throw new Error('Image unavailable');
  return URL.createObjectURL(await res.blob());
}
async function loadImages(version) {
  const trial = currentState.current;
  imageReady = camReady = false; assetError = null;
  $('image-error').hidden = true; $('image-loading').hidden = false;
  $('product-image').hidden = true; $('zoom-button').disabled = true;
  updateAnswerButton();
  const jobs = [loadOne('original', trial.image_url, $('product-image'), version)];
  if (trial.ai) jobs.push(loadOne('ai', trial.ai.gradcam_url, $('heatmap-image'), version));
  await Promise.all(jobs);
}
async function loadOne(kind, path, img, version) {
  let url = null;
  try {
    url = await loadBlob(path);
    if (version !== renderVersion) { URL.revokeObjectURL(url); return; }
    img.src = url;
    await img.decode();
    await api(`/api/trials/${currentState.current.id}/ready`, { phase: kind });
    if (version !== renderVersion) { URL.revokeObjectURL(url); return; }
    if (kind === 'original') {
      originalURL = url; imageReady = true; img.hidden = false;
      $('image-loading').hidden = true; $('zoom-button').disabled = false;
    } else { camURL = url; camReady = true; }
  } catch (error) {
    if (url) URL.revokeObjectURL(url);
    if (version !== renderVersion) return;
    assetError = kind === 'ai' ? 'heatmap_load_error' : 'image_load_error';
    $('image-error-copy').textContent = kind === 'ai' ? 'The AI heatmap could not be loaded or acknowledged. Retry, or record this as an image problem.' : 'The product photo could not be loaded or acknowledged. Retry, or record this as an image problem.';
    $('image-error').hidden = false;
    $('image-loading').hidden = true;
  } finally { if (version === renderVersion) updateAnswerButton(); }
}
function render(state) {
  currentState = state; renderVersion += 1;
  const version = renderVersion;
  releaseImages(); imageReady = camReady = false; assetError = null;
  if (state.status === 'attention') {
    showSection('attention');
    $('attention-feedback').hidden = !state.attention_failures;
    return;
  }
  if (state.status === 'survey') { showSection('survey'); return; }
  if (state.status === 'completed') {
    showSection('complete');
    $('completion-participant').textContent = state.participant_code;
    $('complete-copy').textContent = `${state.participant_code} · ${condition === 'ai' ? 'With AI' : 'Without AI'} · Run ${state.attempt_no}`;
    return;
  }
  showSection('trial-workspace');
  const trial = state.current;
  if (!trial) { showError('No current trial was returned. Reload to resume.'); return; }
  const review = condition === 'ai' && trial.status === 'review';
  $('code-display').textContent = state.participant_code;
  $('run-display').textContent = `Run ${state.attempt_no} · ${condition === 'ai' ? 'With AI' : 'Without AI'}`;
  $('progress-copy').textContent = `${state.completed_count} of ${state.total} completed`;
  $('progress-percent').textContent = `${Math.round(100*state.completed_count/state.total)}%`;
  $('progress').value = state.completed_count; $('progress').max = state.total;
  $('brand-name').textContent = trial.brand;
  $('trial-position').textContent = `Photo ${trial.position} of ${state.total}`;
  $('step-one').classList.toggle('active', !review);
  $('step-two').classList.toggle('active', review);
  $('step-one').textContent = review ? '✓' : '1';
  $('phase-label').textContent = review ? 'Final judgment' : 'Independent judgment';
  $('phase-kicker').textContent = condition === 'baseline' ? 'YOUR JUDGMENT' : (review ? 'STEP 2 · REVIEW & DECIDE' : 'STEP 1 · YOUR FIRST IMPRESSION');
  $('decision-title').textContent = review ? 'Your final call.' : 'What do you see?';
  $('decision-copy').textContent = review ? 'Consider the AI information. Keep or change your answer; the final decision is yours.' : (condition === 'baseline' ? 'Inspect the photo, choose your answer, and rate your confidence. Submit to move to the next photo.' : 'Inspect the photo and give your best judgment before moving on.');
  $('initial-note').hidden = !review;
  $('initial-note').textContent = review ? `Saved independent answer: ${labelName(trial.initial_label)} · Confidence ${trial.initial_confidence}/5` : '';
  $('answer-form').reset();
  for (const input of document.querySelectorAll('[name="trust"]')) input.required = review && condition === 'ai';
  if (review || (condition === 'baseline' && trial.initial_label)) document.querySelector(`[name="label"][value="${trial.initial_label}"]`).checked = true;
  if (condition === 'baseline' && trial.initial_confidence) document.querySelector(`[name="confidence"][value="${trial.initial_confidence}"]`).checked = true;
  $('final-fields').hidden = !(review || condition === 'baseline');
  $('ai-response-fields').hidden = !(review && condition === 'ai');
  $('ai-panel').hidden = !trial.ai;
  $('confidence-legend').textContent = review ? 'How confident are you in your final answer?' : 'How confident are you in this answer?';
  $('answer-button').textContent = review ? 'Submit final answer →' : (condition === 'ai' ? 'Save answer & view AI →' : 'Submit answer →');
  $('save-hint').textContent = condition === 'baseline' ? 'Submit once to save your response and continue.' : (review ? 'Your answer is saved when you submit.' : 'This independent answer stays fixed after saving.');
  if (trial.ai) {
    $('ai-prediction').textContent = labelName(trial.ai.prediction);
    $('ai-confidence').textContent = `${(100*trial.ai.confidence).toFixed(1)}%`;
  }
  validateReasons();
  loadImages(version).catch(() => showError('Please retry loading the images.'));
}
function validateReasons() {
  const options = [...document.querySelectorAll('[name="reason"]')];
  const active = condition === 'ai' && currentState?.current?.status === 'review';
  const unchanged = $('unchanged-reason');
  const answer = new FormData($('answer-form')).get('label');
  unchanged.disabled = active && answer !== currentState.current.initial_label;
  if (unchanged.disabled) unchanged.checked = false;
  const selected = options.some(input => input.checked);
  for (const input of options) input.setCustomValidity('');
  if (active && !selected) options[0].setCustomValidity('Select at least one reason for your trust or decision.');
  $('reason-help').textContent = unchanged.disabled ? 'You changed your answer, so the unchanged-answer option does not apply.' : 'The unchanged-answer option applies when you keep your independent answer.';
}
$('answer-form').addEventListener('change', validateReasons);
$('participant-code').value = read('pi-a3-participant') || '';
$('start-form').addEventListener('submit', event => {
  event.preventDefault();
  perform(async () => {
    const participantCode = $('participant-code').value.trim();
    let pending;
    try { pending = JSON.parse(read(`${storageKey}-pending`)); } catch { pending = null; }
    // Keep the same request ID on network retry so a start cannot create duplicates.
    if (!pending || pending.participant_code !== participantCode) {
      pending = { participant_code: participantCode, request_id: crypto.randomUUID() };
      write(`${storageKey}-pending`, JSON.stringify(pending));
    }
    const familiarity = $('familiarity').value ? Number($('familiarity').value) : null;
    const result = await api('/api/start', { ...pending, condition, consent: $('consent').checked, familiarity });
    token = result.session_token; write(storageKey, token);
    write('pi-a3-participant', participantCode); remove(`${storageKey}-pending`);
    render(result.state); window.scrollTo({ top: 0, behavior: 'instant' });
  });
});
$('attention-form').addEventListener('submit', event => {
  event.preventDefault();
  perform(async () => {
    render(await api('/api/attention', { answer: new FormData(event.target).get('attention') }));
  });
});
$('answer-form').addEventListener('submit', event => {
  event.preventDefault();
  if ($('answer-button').disabled) return;
  perform(async () => {
    const data = new FormData(event.target);
    const review = condition === 'ai' && currentState.current.status === 'review';
    const payload = { label: data.get('label'), confidence: Number(data.get('confidence')) };
    if (review || condition === 'baseline') Object.assign(payload, { uncertain: $('uncertain').checked, comment: $('trial-comment').value });
    if (review) Object.assign(payload, { trust: data.get('trust') ? Number(data.get('trust')) : null, reasons: data.getAll('reason') });
    const state = await api(`/api/trials/${currentState.current.id}/${review ? 'final' : 'initial'}`, payload);
    render(state);
    window.scrollTo({ top: 0, behavior: 'instant' });
  });
});
$('survey-form').addEventListener('submit', event => {
  event.preventDefault();
  perform(async () => {
    const data = new FormData(event.target);
    render(await api('/api/survey', { workload: Number(data.get('workload')),
      usefulness: data.get('usefulness') ? Number(data.get('usefulness')) : null, feedback: $('feedback').value }));
    window.scrollTo({ top: 0, behavior: 'instant' });
  });
});
$('retry-images').addEventListener('click', () => perform(async () => { releaseImages(); await loadImages(renderVersion); }));
$('skip-image').addEventListener('click', () => perform(async () => {
  if (assetError) {
    render(await api(`/api/trials/${currentState.current.id}/skip`, { reason: assetError }));
    window.scrollTo({ top: 0, behavior: 'instant' });
  }
}));
function newRun() {
  renderVersion++; releaseImages(); token = null; currentState = null;
  remove(storageKey); remove(`${storageKey}-pending`); clearError();
  $('start-form').reset(); $('participant-code').value = read('pi-a3-participant') || '';
  showSection('welcome'); window.scrollTo({ top: 0, behavior: 'instant' });
}
$('new-run').addEventListener('click', newRun);
$('reset-session').addEventListener('click', newRun);
async function resume() {
  await perform(async () => {
    try { render(await api('/api/state')); }
    catch (error) { showSection('recovery'); throw error; }
  });
}
$('retry-session').addEventListener('click', resume);
for (const id of ['instructions-button','read-guide']) $(id)?.addEventListener('click', () => $('instructions-dialog').showModal());
$('close-guide').addEventListener('click', () => $('instructions-dialog').close());
$('zoom-button').addEventListener('click', () => {
  if (!originalURL) return;
  $('zoom-image').src = originalURL; $('zoom-dialog').showModal();
});
$('close-zoom').addEventListener('click', () => $('zoom-dialog').close());
document.addEventListener('keydown', event => {
  if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return;
  if (document.querySelector('dialog[open]') || $('trial-workspace').hidden) return;
  if (['INPUT','TEXTAREA','SELECT','BUTTON','SUMMARY'].includes(event.target.tagName)) return;
  if (event.key === '1' || event.key === '2') {
    const input = document.querySelector(`[name="label"][value="${event.key === '1' ? 'genuine' : 'fake'}"]`);
    input.checked = true; validateReasons(); event.preventDefault();
  }
});
token = read(storageKey);
if (token) resume();
