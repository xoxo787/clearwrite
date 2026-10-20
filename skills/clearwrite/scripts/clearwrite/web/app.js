(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const token = document.querySelector('meta[name="clearwrite-token"]').content;
  const state = {generation:0, result:null, generatedAt:-1, selected:0, busy:false, job:null,
    backends:[], style:null, editing:true, stopped:false};
  const label = {codex:'Codex', claude:'Claude Code', demo:'예시', preserve:'원문 보존 · 모델 요청 없음'};
  const errors = {numbers_units_or_order_changed:'숫자·단위 변경', protected_content_changed:'인용·보호 구간 변경',
    protected_span_overlap:'보호 구간과 겹침', excessive_local_compression:'일부 문장의 과도한 축약',
    excessive_document_compression:'글 전체의 과도한 축약', change_budget_exceeded:'변경량 초과',
    scope_negation_or_modality_changed:'부정·조건·가능성 변경', atomic_plan_rejected:'전체 제안 적용 취소',
    direction_changed:'증감 방향 변경', comparison_operator_changed:'비교 표현 변경'};
  const count = text => Array.from(text).length;
  const current = () => state.result && state.generatedAt === state.generation && state.result.source_text === $('input').value;
  const currentStyle = () => state.style && state.style.source_text === $('input').value &&
    state.style.candidate_text === (current()?state.result.text:null);
  const ready = () => state.backends.some(item => item.id === $('backend').value && item.ready);
  function message(text, kind='') { $('status').textContent=text; $('status').className='status '+kind; }
  async function api(path, data) {
    const options = {headers:{'X-ClearWrite-Token':token}};
    if (data !== undefined) { options.method='POST'; options.headers['Content-Type']='application/json'; options.body=JSON.stringify(data); }
    const response = await fetch(path, options);
    let result;
    try { result=await response.json(); } catch { throw Error('응답을 읽지 못했습니다. 앱이 실행 중인지 확인하세요.'); }
    if (!response.ok) throw Error(result.error || '요청을 완료하지 못했습니다.');
    return result;
  }
  function actions() {
    $('rewrite').disabled=state.busy || state.stopped || ($('mode').value!=='preserve' && !ready());
    $('analyze').disabled=state.busy || state.stopped;
    $('example').disabled=state.busy || state.stopped;
    $('backend').disabled=state.busy || state.stopped;
    $('mode').disabled=state.busy || state.stopped;
    $('persona').disabled=state.busy || state.stopped || $('mode').value==='preserve';
    $('model').disabled=state.busy || state.stopped;
    $('cancel').hidden=!state.busy;
    $('style-analyze').disabled=state.busy || state.stopped || !ready();
    const hasResult=!!current() && !state.busy;
    for (const id of ['copy','save-text']) $(id).disabled=!hasResult;
    $('save-report').disabled=state.busy || !(current() || currentStyle());
    const navigable=hasResult && state.result.changes.length>0;
    $('previous-change').disabled=!navigable;
    $('next-change').disabled=!navigable;
  }
  function busy(value) { state.busy=value; actions(); }
  function personaSummary() {
    const option=$('persona').selectedOptions[0];
    const summary=$('persona-summary'); summary.replaceChildren();
    if ($('mode').value==='preserve') { summary.textContent='원문 보존 기준에서는 페르소나를 적용하지 않습니다.'; return; }
    const name=document.createElement('strong'); name.textContent=option.textContent;
    summary.append(name,document.createTextNode(' — '+option.dataset.summary+' 숫자·부정·인용 보존 검사는 모든 페르소나에 똑같이 적용됩니다.'));
  }
  function showOriginal(editing) {
    state.editing=editing;
    $('input').hidden=!editing;
    $('original-diff').hidden=editing;
    $('edit-toggle').textContent=editing?'변경 표시':'원문 편집';
  }
  function selectChange(id, focus=false) {
    if (!current()) return;
    if (state.editing) showOriginal(false);
    state.selected=id;
    document.querySelectorAll('[data-change]').forEach(element => {
      const selected=Number(element.dataset.change)===id;
      element.classList.toggle('active',selected);
      if (element.classList.contains('change-item')) element.setAttribute('aria-pressed',String(selected));
    });
    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const panes=[$('original-diff'),$('result'),$('changes')];
    for (const pane of panes) {
      const element=pane.querySelector(`[data-change="${id}"]`);
      if (!element) continue;
      const target=element.getBoundingClientRect(), bounds=pane.getBoundingClientRect();
      const top=pane.scrollTop+target.top-bounds.top-(pane.clientHeight-target.height)/2;
      pane.scrollTo({top:Math.max(0,top),behavior:reduced?'auto':'smooth'});
    }
    const workspace=document.querySelector('.workspace'), bounds=workspace.getBoundingClientRect();
    const tops=panes.map(pane=>pane.getBoundingClientRect().top);
    // Fit the desktop comparison once; stacked mobile panes keep their page position.
    if (Math.max(...tops)-Math.min(...tops)<1 && bounds.height<=window.innerHeight &&
        (bounds.top<0 || bounds.bottom>window.innerHeight)) {
      workspace.scrollIntoView({block:'nearest',behavior:reduced?'auto':'smooth'});
    }
    if (focus) document.querySelector(`#changes [data-change="${id}"]`)?.focus({preventScroll:true});
  }
  function segments(element, parts) {
    element.replaceChildren();
    for (const part of parts) {
      if (part.change_id === null) { element.append(document.createTextNode(part.text)); continue; }
      const deletion=part.kind==='deletion_marker';
      const marker=deletion || part.kind==='insertion_marker';
      const mark=document.createElement(marker?'button':'mark');
      mark.className=marker?'change-marker '+part.kind:'edit-mark '+part.kind;
      mark.dataset.change=String(part.change_id);
      mark.textContent=part.text;
      if (marker) mark.dataset.label=deletion?'삭제':'추가';
      mark.setAttribute('aria-label',`수정 ${part.change_id}: ${marker?(deletion?'삭제된 표현 확인':'추가 위치 확인'):part.text.trim()||'공백 또는 줄바꿈 변경'}`);
      if (!marker) { mark.tabIndex=0; mark.setAttribute('role','button'); }
      if (!part.text.trim() && !marker) { mark.dataset.space='true'; mark.dataset.symbol=part.text.includes('\n')?'↵':'·'; }
      mark.addEventListener('click',() => selectChange(part.change_id));
      mark.addEventListener('keydown',event => {
        if (event.key==='Enter' || event.key===' ') { event.preventDefault(); selectChange(part.change_id); }
      });
      element.append(mark);
    }
  }
  function short(text) { return count(text)>170?Array.from(text).slice(0,170).join('')+'…':text; }
  function reasons(result) {
    $('changes').replaceChildren();
    for (const change of result.changes) {
      const button=document.createElement('button');
      button.className='change-item'; button.dataset.change=String(change.id); button.setAttribute('aria-pressed','false');
      const title=document.createElement('span'); title.className='change-title';
      const number=document.createElement('span'); number.className='change-number'; number.textContent=change.id;
      title.append(number,document.createTextNode('수정 이유'));
      const from=document.createElement('span'); from.className='change-from'; from.textContent=short(change.original).trim()||'(공백·줄바꿈)';
      const to=document.createElement('span'); to.className='change-to';
      const highlighted=document.createElement('span'); highlighted.textContent=short(change.replacement).trim()||'(삭제)'; to.append(highlighted);
      const why=document.createElement('span'); why.className='change-why'; why.textContent=change.reason;
      button.append(title,from,to,why); button.addEventListener('click',() => selectChange(change.id));
      $('changes').append(button);
    }
    if (!result.changes.length) {
      const paragraph=document.createElement('p'); paragraph.className='empty-reasons';
      paragraph.textContent=result.status==='blocked'?'보존 검사에서 제안이 차단되었습니다. 원문을 유지했습니다. 아래 검수 기록에서 사유를 확인하세요.':'적용할 수정이 없습니다. 그대로 두는 것도 정상적인 윤문 결과입니다.';
      $('changes').append(paragraph);
    }
  }
  function render(result, generation) {
    if (generation !== state.generation || result.source_text !== $('input').value) return;
    state.result=result; state.generatedAt=generation; state.selected=0;
    resetStyle();
    $('result').classList.remove('stale');
    $('demo-badge').hidden=!result.demonstration;
    segments($('original-diff'),result.before_segments); segments($('result'),result.after_segments);
    reasons(result); $('edit-toggle').hidden=false; showOriginal(false);
    $('result-count').textContent=`${count(result.text).toLocaleString()}자 · ${label[result.backend]||'로컬 검사'}${result.persona&&result.backend!=='preserve'?' · '+result.persona.label:''}`;
    const dropped=result.status==='edited'?result.rejected_edits.length:0;
    $('change-count').textContent=`${result.changes.length}곳`;
    const stats=result.change_statistics;
    $('change-rate').textContent=`${stats.rate_percent.toFixed(1)}%`;
    $('change-rate-detail').textContent=`원문 ${stats.original_characters.toLocaleString()}자 → 수정본 ${stats.result_characters.toLocaleString()}자 · 삭제·교체 ${stats.removed_characters}자 / 추가·대체 ${stats.added_characters}자`;
    const verification=result.verification;
    $('verification').textContent=verification.passed?
      `기계적 보존 검사 통과${dropped?` · 제안 ${dropped}곳은 검사에 걸려 제외`:''} · 원문 대비 분량 ${(verification.visible_length_ratio*100).toFixed(1)}% (공백 제외) · 의미와 사실은 마지막으로 대조하세요.`:
      `적용 차단 · ${verification.failures.map(code=>errors[code]||code).join(' · ')} · 원문을 유지했습니다.`;
    $('details').textContent=JSON.stringify(result,null,2);
    $('analysis-summary').textContent=`로컬 규칙 후보 점수 ${result.before.ai_style_score} → ${result.after.ai_style_score} / 100. 모델 문체 점수와 별개의 편집 후보 지표입니다.`;
    message(result.status==='blocked'?'보존 검사에 걸려 원문을 유지했습니다. 수정 제안과 차단 이유를 확인하세요.':
      (result.changes.length?`${result.changes.length}곳을 다듬었습니다.${dropped?` 다른 제안 ${dropped}곳은 보존 검사에 걸려 적용하지 않았습니다.`:''} 형광펜 구간을 선택해 이유를 확인하세요.`:'수정할 필요가 없는 글로 판단해 원문을 유지했습니다.'),result.status==='blocked'?'error':'success');
    actions(); if (result.changes.length) selectChange(result.changes[0].id);
  }
  function resetStyle() {
    state.style=null;
    if (current()) delete state.result.style_assessment;
    $('details').textContent=current()?JSON.stringify(state.result,null,2):'';
    for (const suffix of ['before','after']) {
      $('ai-'+suffix).textContent='미분석';
      $('ai-'+suffix+'-detail').textContent=suffix==='before'?'분석 후 판단 근거가 표시됩니다.':'윤문 후 원문과 함께 분석할 수 있습니다.';
      $('style-'+suffix+'-reasons').replaceChildren();
    }
    $('style-status').textContent='모델 분석 전 · 원문만 넣어도 분석할 수 있습니다.';
  }
  function renderStyle(result, generation) {
    if (generation!==state.generation || result.source_text!==$('input').value ||
        result.candidate_text!==(current()?state.result.text:null)) return;
    state.style=result;
    const categories={repetition:'반복',formulaic:'상투적 표현',uniformity:'획일적 흐름',abstraction:'추상적 부연'};
    for (const suffix of ['before','after']) {
      const assessment=result[suffix], target=$('style-'+suffix+'-reasons'); target.replaceChildren();
      $('ai-'+suffix).textContent=assessment?String(assessment.score):'미분석';
      $('ai-'+suffix+'-detail').textContent=assessment?assessment.summary:'수정본이 없습니다. 윤문한 뒤 다시 분석하세요.';
      if (!assessment) continue;
      const dimensions=document.createElement('p'); dimensions.className='style-dimensions';
      dimensions.textContent=Object.entries(assessment.dimensions).map(([key,value])=>`${categories[key]} ${value}/25`).join(' · ');
      target.append(dimensions);
      for (const reason of assessment.reasons) {
        const item=document.createElement('div'); item.className='style-reason';
        const quote=document.createElement('blockquote'); quote.textContent=reason.quote;
        const explanation=document.createElement('p'); explanation.textContent=reason.reason;
        item.append(quote,explanation); target.append(item);
      }
    }
    $('style-status').textContent=`${label[result.backend]} · ${result.model==='cli_default'?'CLI 기본 모델':result.model} · 모델 추정${result.reused_identical_text?' · 원문과 수정본이 같아 같은 평가를 표시합니다.':''}`;
    if (current()) state.result.style_assessment=result;
    $('details').textContent=JSON.stringify(current()?state.result:{source_text:result.source_text,style_assessment:result},null,2);
    message('AI 문체 분석을 마쳤습니다. 점수와 실제 인용 근거를 함께 확인하세요.','success');
    actions();
  }
  $('input').placeholder=$('input').placeholder.replace(/\\n/g,'\n');
  $('input').addEventListener('input',() => {
    state.generation++; $('input-count').textContent=`${count($('input').value).toLocaleString()}자`;
    resetStyle(); $('change-rate').textContent='—'; $('change-rate-detail').textContent='원문이 바뀌었습니다. 다시 윤문하면 계산합니다.'; $('demo-badge').hidden=true;
    if (state.result) { $('result').classList.add('stale'); message('원문이 바뀌었습니다. 이전 결과를 복사하려면 원문을 되돌리거나 다시 윤문하세요.'); }
    else message($('input').value.trim()?'모델을 선택하고 전송 동의 후 윤문하세요.':'글을 붙여 넣거나 예시를 열어 시작하세요.');
    $('edit-toggle').hidden=true; showOriginal(true); actions();
    if (state.job) api(`/api/jobs/${state.job}/cancel`,{}).catch(()=>{});
  });
  $('edit-toggle').onclick=() => showOriginal(!state.editing);
  $('backend').onchange=() => { $('model-consent').checked=false; connection(); };
  $('mode').onchange=() => { personaSummary(); actions(); };
  $('persona').onchange=personaSummary;
  personaSummary();
  $('model-consent').onchange=() => $('permission').classList.remove('attention');
  function connection() {
    const item=state.backends.find(item=>item.id===$('backend').value);
    $('connection').textContent=item?`${item.name}${item.version?' · '+item.version:''} · ${item.message}`:'연결할 CLI가 없습니다.';
    actions();
  }
  async function job(data, generation, onResult) {
    busy(true); let identifier;
    try {
      const created=await api('/api/jobs',data); identifier=created.job_id; state.job=identifier;
      if (generation!==state.generation) { await api(`/api/jobs/${identifier}/cancel`,{}); return; }
      const started=Date.now();
      while (state.job===identifier) {
        await new Promise(resolve=>setTimeout(resolve,450));
        const result=await api(`/api/jobs/${identifier}`);
        if (generation!==state.generation) return;
        if (result.state==='completed') { onResult(result.result); return; }
        if (result.state==='failed' || result.state==='cancelled') throw Error(result.error||'요청을 완료하지 못했습니다.');
        message(`${data.action==='style'?label[data.backend]+'에서 AI 문체 분석':data.mode==='preserve'?'로컬에서 원문 보존 검사':label[data.backend]+'에서 윤문'} 중… ${Math.floor((Date.now()-started)/1000)}초`,'loading');
      }
    } catch (error) {
      if (generation===state.generation) message(error.message||'요청에 실패했습니다.','error');
    } finally {
      if (!identifier || state.job===identifier) state.job=null;
      busy(false);
    }
  }
  $('rewrite').onclick=async() => {
    if (!$('input').value.trim()) { message('먼저 다듬을 글을 넣어 주세요.','error'); $('input').focus(); return; }
    if ($('mode').value!=='preserve' && !$('model-consent').checked) {
      $('permission').classList.add('attention'); message('원문을 보낼 모델 서비스를 확인하고 전송에 동의해 주세요.','error'); $('model-consent').focus(); return;
    }
    const generation=state.generation;
    message($('mode').value==='preserve'?'로컬에서 원문 보존 검사 중…':`${label[$('backend').value]}에서 글을 다듬고 있습니다…`,'loading');
    await job({action:'rewrite',text:$('input').value,backend:$('backend').value,mode:$('mode').value,
      persona:$('persona').value,model:$('model').value.trim(),allow_model:$('model-consent').checked},generation,result=>render(result,generation));
    $('model-consent').checked=false;
  };
  $('cancel').onclick=async() => {
    if (!state.job) return;
    try { await api(`/api/jobs/${state.job}/cancel`,{}); message('요청을 취소하고 있습니다. 이미 처리된 서비스 사용량은 남을 수 있습니다.','loading'); }
    catch (error) { message(error.message,'error'); }
  };
  $('example').onclick=async() => {
    busy(true);
    try {
      const result=await api('/api/example');
      $('input').value=result.source_text; state.generation++; $('input-count').textContent=`${count(result.source_text)}자`;
      $('model-consent').checked=false; resetStyle();
      render(result,state.generation);
    } catch(error) { message(error.message,'error'); }
    finally { busy(false); }
  };
  $('analyze').onclick=async() => {
    if (!$('input').value.trim()) { message('분석할 글을 넣어 주세요.','error'); $('input').focus(); return; }
    const generation=state.generation; busy(true); message('로컬 문체 분석 중…','loading');
    try {
      const result=await api('/api/process',{action:'analyze',text:$('input').value});
      if (generation!==state.generation) return;
      $('analysis-summary').textContent=`편집 후보 ${result.findings.length}곳 · 로컬 규칙 후보 점수 ${result.ai_style_score}/100 (모델 문체 점수와 별개)`;
      $('details').textContent=JSON.stringify(result,null,2); $('analysis-summary').parentElement.open=true;
      message('문체 분석을 마쳤습니다. 모델 요청은 보내지 않았습니다.','success');
    } catch(error) { message(error.message,'error'); }
    finally { busy(false); }
  };
  $('style-analyze').onclick=async() => {
    if (!$('input').value.trim()) { message('분석할 글을 넣어 주세요.','error'); $('input').focus(); return; }
    if (!$('model-consent').checked) {
      $('permission').classList.add('attention'); message('선택한 모델로 원문과 수정본을 전송하는 데 동의해 주세요.','error'); $('model-consent').focus(); return;
    }
    const generation=state.generation;
    resetStyle();
    $('style-status').textContent=`${label[$('backend').value]}에서 분석 중…`;
    message(`${label[$('backend').value]}에서 문체와 판단 이유를 분석합니다…`,'loading');
    await job({action:'style',text:$('input').value,candidate:current()?state.result.text:null,
      backend:$('backend').value,model:$('model').value.trim(),allow_model:true},generation,result=>renderStyle(result,generation));
    if (generation===state.generation && !state.style) $('style-status').textContent='분석을 완료하지 못했습니다. 점수는 미분석이며 윤문 결과는 유지됩니다.';
    $('model-consent').checked=false;
  };
  $('copy').onclick=async() => {
    if (!current()) return;
    try { await navigator.clipboard.writeText(state.result.text); message('수정본을 복사했습니다.','success'); }
    catch { message('복사 권한이 없습니다. 수정본을 직접 선택해 복사해 주세요.','error'); }
  };
  function download(text,name,type) {
    const url=URL.createObjectURL(new Blob([text],{type})); const anchor=document.createElement('a');
    anchor.href=url; anchor.download=name; anchor.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  $('save-text').onclick=() => { if(current()) download(state.result.text,'clearwrite-edited.txt','text/plain;charset=utf-8'); };
  $('save-report').onclick=() => {
    const report=current()?state.result:currentStyle()?{source_text:state.style.source_text,style_assessment:state.style}:null;
    if (report) download(JSON.stringify(report,null,2),'clearwrite-report.json','application/json');
  };
  $('previous-change').onclick=() => { if(current()) selectChange(Math.max(1,state.selected-1),true); };
  $('next-change').onclick=() => { if(current()) selectChange(Math.min(state.result.changes.length,state.selected+1),true); };
  $('shutdown').onclick=async() => {
    if (!window.confirm('ClearWrite를 종료할까요? 저장하지 않은 글은 이 창에만 남습니다.')) return;
    try { await api('/api/shutdown',{}); state.stopped=true; busy(false); $('shutdown').disabled=true; message('앱을 종료했습니다. 다시 사용하려면 ClearWrite 실행 파일을 여세요.'); }
    catch(error) { message(error.message,'error'); }
  };
  api('/api/status').then(result=>{
    state.backends=result.backends;
    for (const item of result.backends) { const option=document.querySelector(`#backend option[value="${item.id}"]`); option.disabled=!item.ready; option.textContent=item.name+(item.ready?'':' · '+(item.installed?'업데이트 필요':'설치 필요')); }
    $('backend').value=result.default_backend; connection();
    actions();
  }).catch(error=>{ $('connection').textContent='모델 연결 확인 실패'; message(error.message,'error'); actions(); });
})();
