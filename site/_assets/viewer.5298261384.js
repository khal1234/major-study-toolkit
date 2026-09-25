

function esc(s){
  return String(s).replace(/[&<>]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];
  });
}

var viewerSettingsKey = 'thermo:viewer-settings:v1';
var viewerSettingDefaults = {
  reviewHighlights:false,
  reviewHideDrill:true,
  readerScale:1,
  shuffleProblems:false,
  wrongOnlyProblems:false,
  derivSlideMode:true,
  spotSlideMode:true
};
var chapterStoragePrefix = (CH.subject || 'thermo') + ':ch' + String(CH.chapterNumber).padStart(2, '0');
function readStoredJson(key, fallback){
  try {
    var value = JSON.parse(localStorage.getItem(key) || 'null');
    return value && typeof value === 'object' && !Array.isArray(value) ? value : fallback;
  } catch(ignore) { return fallback; }
}
function writeStoredJson(key, value){
  try { localStorage.setItem(key, JSON.stringify(value)); } catch(ignore) {}
}
var storedViewerSettings = readStoredJson(viewerSettingsKey, {});
var viewerSettings = {};
Object.keys(viewerSettingDefaults).forEach(function(key){
  viewerSettings[key] = Object.prototype.hasOwnProperty.call(storedViewerSettings, key)
    ? storedViewerSettings[key] : viewerSettingDefaults[key];
});
var chapterLearning = readStoredJson(chapterStoragePrefix + ':learning:v1', {});
function saveViewerSettings(){ writeStoredJson(viewerSettingsKey, viewerSettings); }
function updateViewerSettings(patch){
  Object.keys(patch).forEach(function(key){
    if(!Object.prototype.hasOwnProperty.call(viewerSettingDefaults, key)) throw new Error('등록되지 않은 보기 설정: ' + key);
    viewerSettings[key] = patch[key];
  });
  saveViewerSettings();
}
function saveChapterLearning(){
  writeStoredJson(chapterStoragePrefix + ':learning:v1', {
    probMarks: probMarks || {},
    oxPicks: oxPicks || {},
    recapPicks: recapPicks || {},
    probOrder: probOrder || null,
    reviewCursor: reviewCursor || null
  });
}
var reviewCursor = (chapterLearning.reviewCursor && typeof chapterLearning.reviewCursor === 'object')
  ? chapterLearning.reviewCursor : null;

function renderCourseTree(){
  var current = Number(CH.chapterNumber);
  var visibleSubjects = COURSE_TREE.filter(function(s){ return s.name === CURRENT_SUBJECT; });
  document.getElementById('courseTree').innerHTML = visibleSubjects.map(function(subj){
    var isCur = true;
    var chaps = subj.chapters.map(function(ch){
      var num = String(ch.number).padStart(2, '0');
      var inner = '<span class="chapter-no">' + num + '</span>' +
        '<span class="chapter-title">' + esc(ch.title) +
        (ch.status === 'reviewing' ? '<span class="chapter-status">검수 중</span>' : '') + '</span>';
      if(!ch.built){
        return '<div class="chapter-link disabled">' + inner + '</div>';
      }
      var href = esc(ch.fname);
      var cls = 'chapter-link' + (isCur && ch.number === current ? ' current' : '') +
        (ch.status === 'reviewing' ? ' reviewing' : '');
      return '<a class="' + cls + '" href="' + href + '">' + inner + '</a>';
    }).join('');
    return '<details class="ct-subj"' + (isCur ? ' open' : '') + '>' +
      '<summary class="ct-head"><span class="ct-name">' + esc(subj.name) +
      '</span><span class="ct-chev">▸</span></summary>' +
      '<div class="ct-chaps">' + chaps + '</div></details>';
  }).join('');
}
function setCoursePane(open){
  document.getElementById('coursePane').classList.toggle('open', open);
  document.getElementById('courseScrim').classList.toggle('open', open);
  document.querySelectorAll('[data-course-menu]').forEach(function(b){
    b.setAttribute('aria-expanded', String(open));
  });
}
renderCourseTree();
(function(){
  var link = document.getElementById('courseHomeLink');
  if(!link) return;
  var host = location.hostname;
  if(host === 'localhost' || host === '127.0.0.1'){
    link.href = location.protocol + '//' + host + ':8800/index.html';
  }
})();
document.querySelectorAll('[data-course-menu]').forEach(function(btn){
  btn.addEventListener('click', function(){
    setCoursePane(!document.getElementById('coursePane').classList.contains('open'));
  });
});
(function(){
  var anchor = document.querySelector('.cover-actions');
  if (!anchor) return;
  var queued = false;
  function sync(){
    queued = false;
    var r = anchor.getBoundingClientRect();
    document.documentElement.classList.toggle('cover-out', r.bottom <= 0 || r.height === 0);
  }
  function schedule(){
    if (queued) return;
    queued = true;
    setTimeout(sync, 0);
  }
  window.addEventListener('scroll', schedule, {passive: true});
  document.addEventListener('scroll', schedule, {passive: true, capture: true});
  window.addEventListener('resize', schedule, {passive: true});
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(schedule, {threshold: 0}).observe(anchor);
  }
  sync();
})();
document.getElementById('courseScrim').addEventListener('click', function(){ setCoursePane(false); });
var persistentCoursePane = window.matchMedia('(min-width:1320px)');
function syncCoursePaneMode(e){
  document.getElementById('coursePane').classList.toggle('drawer-mode', !e.matches);
  setCoursePane(false);
}
syncCoursePaneMode(persistentCoursePane);
if(persistentCoursePane.addEventListener) persistentCoursePane.addEventListener('change', syncCoursePaneMode);
else persistentCoursePane.addListener(syncCoursePaneMode);

var review = CH._reviewChanges || {summary:{added:0, modified:0, deleted:0}};
var reviewEnabled = viewerSettings.reviewHighlights === true;
var reviewHideDrill = viewerSettings.reviewHideDrill !== false;
var REVIEW_DRILL_PAGES = ['practice', 'problems'];
function reviewHasChanges(){
  var s = review.summary || {};
  return Boolean(s.added || s.modified || s.deleted);
}
function reviewChanged(item, field){
  var changed = item && item._changed;
  return Boolean(changed && (changed.indexOf('new') >= 0 || changed.indexOf(field) >= 0));
}
function reviewLevelClass(level){
  return level === 'minor' ? ' rv-minor' : '';
}
function reviewGranular(item, field){
  var granular = item && item._granular;
  return Boolean(granular && granular.indexOf(field) >= 0);
}
function reviewClass(item, field){
  if(reviewGranular(item, field)) return '';
  if(!reviewChanged(item, field)) return '';
  return ' review-mark' + reviewLevelClass(item && item._changeLevel)
    + '" data-change-note="' + reviewNoteText(item);
}
function reviewParaClass(item, field, index){
  var paras = item && item._changedParas && item._changedParas[field];
  if(!(paras && paras.indexOf(index) >= 0)) return '';
  return ' review-mark' + reviewLevelClass(item && item._changeLevel)
    + '" data-change-note="' + reviewNoteText(item);
}
function reviewNoteText(item){
  var note = item && item.changeNote;
  return note ? esc(String(note)).replace(/"/g, '&quot;') : '';
}
function reviewClassOwned(item, field, owner){
  var frag = reviewClass(item, field);
  return (frag && !reviewNoteText(item)) ? frag + reviewNoteText(owner) : frag;
}
function reviewNote(item){
  var note = reviewNoteText(item);
  return note ? ' data-change-note="' + note + '"' : '';
}
function viewerChangesKey(){
  return chapterStoragePrefix + ':viewer-seen:'
       + (VIEWER_CHANGES || []).map(function(c){ return c.at + '|' + c.what; }).join('~');
}
function syncViewerChanges(){
  var box = document.getElementById('viewerChanges');
  if(!box) return;
  var list = VIEWER_CHANGES || [];
  var seen = false;
  try { seen = localStorage.getItem(viewerChangesKey()) === '1'; } catch(ignore) {}
  box.hidden = !(reviewEnabled && list.length && !seen);
  if(box.hidden) return;
  document.getElementById('viewerChangesList').innerHTML = list.map(function(c){
    return '<li>' + esc(c.what)
      + (c.where ? ' <span class="vc-where">— ' + esc(c.where) + '</span>' : '') + '</li>';
  }).join('');
}
document.addEventListener('click', function(ev){
  if(!ev.target || ev.target.id !== 'viewerChangesOk') return;
  try { localStorage.setItem(viewerChangesKey(), '1'); } catch(ignore) {}
  document.getElementById('viewerChanges').hidden = true;
});
function syncReviewTools(){
  var summary = review.summary || {};
  var tools = document.getElementById('reviewTools');
  var toggle = document.getElementById('reviewToggle');
  syncViewerChanges();
  tools.hidden = !(reviewHasChanges() || (VIEWER_CHANGES || []).length);
  toggle.classList.toggle('on', reviewEnabled);
  toggle.textContent = '변경점 표시: ' + (reviewEnabled ? '켜짐' : '꺼짐');
  var visiblePlan = reviewPlan();
  var foldedAway = visiblePlan.foldedAway || 0;
  var parts = [];
  if(summary.added) parts.push('추가 ' + summary.added);
  if(visiblePlan.length) parts.push('수정 ' + visiblePlan.length);
  if(summary.deleted) parts.push('삭제 ' + summary.deleted);
  if(foldedAway) parts.push('같은 사유 ' + foldedAway + ' 접힘');
  var summaryEl = document.getElementById('reviewSummary');
  summaryEl.textContent = parts.join(' · ');
  summaryEl.title = parts.length ? '이번 변경: ' + parts.join(' · ') : '';
  document.documentElement.classList.toggle('review-mode', reviewEnabled);
  document.documentElement.classList.toggle('review-hide-drill', reviewHideDrill);
  var drillBtn = document.getElementById('reviewDrill');
  var drillHidden = reviewHideDrill
    ? (function(){ reviewHideDrill = false; var all = reviewPlan().length;
                   reviewHideDrill = true; return all - reviewPlan().length; })()
    : 0;
  drillBtn.hidden = true;
  drillBtn.classList.toggle('on', reviewHideDrill);
  drillBtn.textContent = reviewHideDrill
    ? '연습·문제 ' + drillHidden + ' 숨김' : '연습·문제 표시 중';
  drillBtn.setAttribute('aria-pressed', reviewHideDrill ? 'true' : 'false');
  syncReviewNavigation();
}
var reviewNavIndex = -1;
function reviewOutermost(list){
  return list.filter(function(el){
    return !list.some(function(other){ return other !== el && other.contains(el); });
  });
}
function reviewTargets(){
  return reviewOutermost(Array.from(document.querySelectorAll('.review-mark, .review-diagram')));
}
function reviewCardHasChange(item){
  if(!item) return false;
  if(item._changed && item._changed.length) return true;
  return (item.diagrams || []).some(function(d){ return d._reviewChanged; });
}
function reviewPlan(){
  var plan = [];
  Array.from(document.querySelectorAll('.page[data-page]')).forEach(function(page){
    var name = page.getAttribute('data-page');
    if(hiddenPages.indexOf(name) >= 0) return;
    if(name === 'derivation' || name === 'practice'){
      var items = (name === 'derivation'
        ? ((CH.derivation && CH.derivation.formulas) || []) : pracDeck());
      items.forEach(function(item, i){
        if(!reviewCardHasChange(item)) return;
        plan.push({page:name, index:i});
      });
      return;
    }
    reviewOutermost(Array.from(page.querySelectorAll('.review-mark, .review-diagram')))
      .forEach(function(el){ plan.push({page:name, el:el}); });
  });
  return reviewFoldPlan(plan);
}
function reviewRevealTarget(el){
  if(!el || !el.parentElement) return el;
  for(var n = el.parentElement; n && n !== document.body; n = n.parentElement){
    if(n.tagName === 'DETAILS' && !n.open) n.open = true;
  }
  var wholeCardIsNew = el.classList && el.classList.contains('review-mark');
  Array.prototype.forEach.call(el.querySelectorAll ? el.querySelectorAll('details') : [],
    function(d){
      if(d.open) return;
      if(wholeCardIsNew || d.querySelector('.review-mark, .review-diagram')) d.open = true;
    });
  return el;
}
function reviewShowPlanEntry(entry){
  showPage(entry.page);
  if(entry.index === undefined) return reviewRevealTarget(entry.el);
  if(entry.page === 'derivation'){ derivIndex = entry.index; renderDerivCard(); }
  else { pracIndex = entry.index; renderPracCard(); }
  var page = document.querySelector('.page[data-page="' + entry.page + '"]');
  if(!page) return null;
  var found = reviewOutermost(Array.from(page.querySelectorAll('.review-mark, .review-diagram')));
  return reviewRevealTarget(found[0] || page);
}
function reviewNoteFor(el){
  var notes = [];
  var self = el.getAttribute('data-change-note');
  if(self) notes.push(self);
  el.querySelectorAll('[data-change-note]').forEach(function(n){
    var v = n.getAttribute('data-change-note');
    if(v && notes.indexOf(v) < 0) notes.push(v);
  });
  return notes.join('\n· ');
}
var REVIEW_CLASS_STOPS = 3;
var REVIEW_ITEM_SEL = '.fcard, .qcard, .pcard, .q-card, [id^="theory-sec-"]';
function reviewNoteKey(note){
  var m = /^지적\([^)]*\)/.exec(note || '');
  return m ? m[0] : (note || '');
}
function reviewEntryNote(entry){
  if(entry.el) return reviewNoteFor(entry.el) || '';
  var items = (entry.page === 'derivation'
    ? ((CH.derivation && CH.derivation.formulas) || []) : pracDeck());
  var item = items[entry.index];
  return (item && item.changeNote) ? String(item.changeNote) : '';
}
function reviewNoteSeenBefore(key){
  return (typeof REVIEW_NOTE_SEEN === 'object' && REVIEW_NOTE_SEEN && REVIEW_NOTE_SEEN[key]) || 0;
}
function reviewFoldPlan(plan){
  var total = {}, seen = {}, out = [];
  plan.forEach(function(e){
    e.note = reviewEntryNote(e);
    e.noteKey = reviewNoteKey(e.note);
    if(e.note) total[e.noteKey] = (total[e.noteKey] || 0) + 1;
  });
  plan.forEach(function(e){
    if(e.el && e.el.hasAttribute && e.el.hasAttribute('data-note-quiet')) return;
    if(!e.note){ e.groupRank = 1; e.groupTotal = 1; out.push(e); return; }
    if(seen[e.noteKey] === undefined) seen[e.noteKey] = reviewNoteSeenBefore(e.noteKey);
    var rank = seen[e.noteKey] = seen[e.noteKey] + 1;
    e.groupRank = rank;
    e.groupTotal = total[e.noteKey] + reviewNoteSeenBefore(e.noteKey);
    if(rank <= REVIEW_CLASS_STOPS) out.push(e);
  });
  out.foldedAway = plan.length - out.length;
  return out;
}
function reviewFoldDuplicateNotes(){
  var owners = [], sets = [];
  Array.prototype.forEach.call(document.querySelectorAll('[data-change-note]'), function(el){
    el.removeAttribute('data-note-quiet');
    if(el.classList.contains('review-diagram')) return;
    var note = el.getAttribute('data-change-note');
    if(!note) return;
    for(var p = el.parentElement; p; p = p.parentElement){
      if(p.getAttribute && p.getAttribute('data-change-note') === note){
        el.setAttribute('data-note-quiet', ''); return;
      }
    }
    var owner = (el.parentElement && el.parentElement.closest(REVIEW_ITEM_SEL))
      || el.parentElement || document.body;
    var at = owners.indexOf(owner);
    if(at < 0){ at = owners.push(owner) - 1; sets.push({}); }
    sets[at][note] = (sets[at][note] || 0) + 1;
    if(sets[at][note] > REVIEW_CLASS_STOPS){ el.setAttribute('data-note-quiet', ''); return; }
  });
  var shown = {};
  Array.prototype.forEach.call(
    document.querySelectorAll('.review-mark[data-change-note], .review-diagram[data-change-note]'),
    function(el){
      if(el.classList.contains('review-diagram')) return;
      if(el.hasAttribute('data-note-quiet')) return;
      var key = reviewNoteKey(el.getAttribute('data-change-note'));
      if(!key) return;
      if(shown[key] === undefined) shown[key] = reviewNoteSeenBefore(key);
      shown[key] = shown[key] + 1;
      if(shown[key] > REVIEW_CLASS_STOPS) el.setAttribute('data-note-quiet', '');
    });
  reviewJoinAdjacentMarks();
}
var reviewNoteFoldPending = false;
function reviewScheduleNoteFold(){
  if(reviewNoteFoldPending) return;
  reviewNoteFoldPending = true;
  requestAnimationFrame(function(){
    reviewNoteFoldPending = false;
    reviewFoldDuplicateNotes();
  });
}
function reviewPlanFingerprint(plan){
  function id(e){
    if(!e) return '';
    return e.page + ':' + (e.index !== undefined ? '#' + e.index : (e.note || '').slice(0, 24));
  }
  return plan.length + '|' + id(plan[0]) + '|' + id(plan[plan.length - 1]);
}
var reviewCursorSaved = '';
function saveReviewCursor(plan){
  if(!reviewNavLanded || !plan.length) return;
  var payload = JSON.stringify({i:reviewNavIndex, fp:reviewPlanFingerprint(plan)});
  if(payload === reviewCursorSaved) return;
  reviewCursorSaved = payload;
  reviewCursor = JSON.parse(payload);
  saveChapterLearning();
}
function restoreReviewCursor(){
  if(!reviewCursor || typeof reviewCursor.i !== 'number') return;
  var plan = reviewPlan();
  if(!plan.length) return;
  if(reviewPlanFingerprint(plan) !== reviewCursor.fp || reviewCursor.i < 0
     || reviewCursor.i >= plan.length){ reviewCursor = null; return; }
  reviewNavIndex = reviewCursor.i;
  reviewNavLanded = true;   // 이어서 ▶ 를 누르면 **다음** 것으로 간다(다시 착지하게 하지 않는다)
  syncReviewNavigation();
}
function startReviewNoteFold(){
  reviewFoldDuplicateNotes();
  if(window.MutationObserver){
    new MutationObserver(reviewScheduleNoteFold).observe(document.body, {childList:true, subtree:true});
  }
}
function syncReviewNavigation(){
  var nav = document.getElementById('reviewNav');
  var plan = reviewPlan();
  nav.hidden = !reviewEnabled || !plan.length;
  if(!plan.length){
    reviewNavIndex = -1;
    document.getElementById('reviewNavCount').textContent = '0 / 0';
    return;
  }
  if(reviewNavIndex < 0 || reviewNavIndex >= plan.length) reviewNavIndex = 0;
  var countEl = document.getElementById('reviewNavCount');
  var here = plan[reviewNavIndex] || {};
  countEl.textContent = (reviewNavIndex + 1) + ' / ' + plan.length
    + (plan.foldedAway ? ' · 같은 사유 ' + plan.foldedAway + ' 접힘' : '');
  countEl.title = (here.groupTotal > 1)
    ? '이 부류 ' + here.groupTotal + '건 중 ' + here.groupRank + '번째'
      + (here.groupTotal > REVIEW_CLASS_STOPS
         ? ' — 같은 사유는 앞 ' + REVIEW_CLASS_STOPS + '개만 표시합니다' : '')
    : '';
  saveReviewCursor(plan);
  document.getElementById('reviewPrev').disabled = false;
  document.getElementById('reviewNext').disabled = false;
  var atFirst = reviewNavLanded && reviewNavIndex === 0;
  var homeBtn = document.getElementById('reviewHome');
  homeBtn.classList.toggle('is-home', atFirst);
  homeBtn.setAttribute('aria-disabled', atFirst ? 'true' : 'false');
}
var reviewMoveInFlight = false, reviewSettleTimer = 0, reviewSyncPending = false;
function reviewArmScrollSettle(){
  clearTimeout(reviewSettleTimer);
  reviewSettleTimer = setTimeout(function(){ reviewMoveInFlight = false; }, 180);
}
var reviewLandedEl = null, reviewLandedScroll = -1;
function syncReviewIndexToViewport(){
  if(reviewMoveInFlight) return;   // 이동이 만든 스크롤 도중에는 화면으로 되추론하지 않는다
  var plan = reviewPlan();
  if(!plan.length) return;
  var best = -1;
  if(reviewLandedEl && Math.abs(window.scrollY - reviewLandedScroll) <= 2){
    var lr = reviewLandedEl.getBoundingClientRect();
    if(lr.height || lr.width){                     // 탭이 바뀌어 숨었으면 기억을 버린다
      for(var m = 0; m < plan.length; m++){
        if(plan[m].el === reviewLandedEl){ best = m; break; }
      }
    }
  }
  var stepperIndex = (currentPage === 'derivation') ? derivIndex
                   : (currentPage === 'practice') ? pracIndex : null;
  if(best < 0 && stepperIndex !== null){
    for(var k = 0; k < plan.length; k++){
      if(plan[k].page === currentPage && plan[k].index === stepperIndex){ best = k; break; }
    }
  }
  if(best < 0){
    var anchor = reviewBarOffset(), bestDist = Infinity;
    for(var i = 0; i < plan.length; i++){
      if(!plan[i].el) continue;                       // 스테퍼 항목은 좌표가 없다
      var r = plan[i].el.getBoundingClientRect();
      if(!r.height && !r.width) continue;             // 숨은 페이지는 치수가 0이다
      var d = Math.abs(r.top - anchor);
      if(d < bestDist){ bestDist = d; best = i; }
    }
  }
  if(best >= 0 && best !== reviewNavIndex){
    reviewNavIndex = best;
    syncReviewNavigation();
  }
}
window.addEventListener('scroll', function(){
  if(!reviewEnabled) return;
  if(reviewMoveInFlight){ reviewArmScrollSettle(); return; }  // 버튼이 만든 스크롤과 싸우지 않는다
  if(reviewSyncPending) return;
  reviewSyncPending = true;
  requestAnimationFrame(function(){ reviewSyncPending = false; syncReviewIndexToViewport(); });
}, {passive:true});
function reviewBarOffset(){
  var bar = document.getElementById('tabbar');
  return (bar ? bar.getBoundingClientRect().height : 0) + 8;
}
function scrollElementBelowBar(el, behavior){
  var y = window.scrollY + el.getBoundingClientRect().top - reviewBarOffset();
  window.scrollTo({top: Math.max(0, y), behavior: behavior || 'auto'});
}
var REVIEW_CARD_SELECTOR = '.fcard, .qcard, .pcard, .theory-item';
function reviewLandingAnchor(el){
  var card = el.closest ? el.closest(REVIEW_CARD_SELECTOR) : null;
  if(!card || card === el) return el;
  var room = window.innerHeight - reviewBarOffset();
  var span = el.getBoundingClientRect().bottom - card.getBoundingClientRect().top;
  return span <= room ? card : el;
}
function scrollReviewTargetIntoView(el){
  reviewMoveInFlight = true;
  var anchor = reviewLandingAnchor(el);
  var wanted = window.scrollY + anchor.getBoundingClientRect().top - reviewBarOffset();
  var max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
  reviewLandedEl = el;                 // 착지 판정은 표식으로 — 카드로 바꾸면 카운터가 갈린다
  reviewLandedScroll = Math.min(Math.max(0, wanted), max);
  scrollElementBelowBar(anchor, 'smooth');
  reviewArmScrollSettle();          // 스크롤이 한 번도 안 일어나도(제자리) 잠금이 풀리도록
}
var reviewNavLanded = false;
function reviewAdjacentChapter(step){
  if(!Array.isArray(SUBJECT_NAV)) return null;
  var i = SUBJECT_NAV.findIndex(function(ch){ return ch.number === Number(CH.chapterNumber); });
  if(i < 0) return null;
  var nb = SUBJECT_NAV[i + (step > 0 ? 1 : -1)];
  return nb && nb.href ? nb.href : null;
}
function chapterDataHasChange(node){
  if(!node || typeof node !== 'object') return false;
  if(node._reviewChanged) return true;
  if(node._changed && (!Array.isArray(node._changed) || node._changed.length)) return true;
  if(Array.isArray(node)){
    for(var i = 0; i < node.length; i++){ if(chapterDataHasChange(node[i])) return true; }
    return false;
  }
  for(var k in node){
    if(Object.prototype.hasOwnProperty.call(node, k) && chapterDataHasChange(node[k])) return true;
  }
  return false;
}
function fetchHrefHasChange(href){
  return fetch(href).then(function(res){ return res.text(); }).then(function(html){
    var line = html.split('\n').find(function(ln){ return ln.indexOf('var CH = ') === 0; });
    if(!line) return false;
    var body = line.slice('var CH = '.length).replace(/;\s*$/, '');
    var data;
    try{ data = JSON.parse(body); } catch(e){ return false; }
    return chapterDataHasChange(data);
  }).catch(function(){ return false; });        // 못 읽었으면 «없다» 쪽으로 — 조용히 넘어간다
}
function subjectNavIndexByHref(href){
  return Array.isArray(SUBJECT_NAV) ? SUBJECT_NAV.findIndex(function(ch){ return ch.href === href; }) : -1;
}
function findReviewableChapter(step){
  function tryHref(href){
    if(!href) return Promise.resolve(null);
    return fetchHrefHasChange(href).then(function(has){
      if(has) return href;
      var i = subjectNavIndexByHref(href);
      var nb = i < 0 ? null : SUBJECT_NAV[i + (step > 0 ? 1 : -1)];
      return tryHref(nb && nb.href ? nb.href : null);
    });
  }
  return tryHref(reviewAdjacentChapter(step));
}
var reviewAnnounceTimer = null;
function reviewAnnounce(text){
  var el = document.getElementById('reviewNavCount');
  if(!el) return;
  el.textContent = text;
  el.setAttribute('role', 'status');
  if(reviewAnnounceTimer) clearTimeout(reviewAnnounceTimer);
  reviewAnnounceTimer = setTimeout(function(){ syncReviewNavigation(); }, 3000);
}
function moveReviewTarget(step){
  var plan = reviewPlan();
  if(!plan.length) return;
  syncReviewIndexToViewport();
  if(reviewNavIndex < 0 || reviewNavIndex >= plan.length) reviewNavIndex = 0;
  var n = plan.length;
  var first = !reviewNavLanded;
  reviewNavLanded = true;
  if(!first && ((step > 0 && reviewNavIndex === n - 1) || (step < 0 && reviewNavIndex === 0))){
    findReviewableChapter(step).then(function(hop){
      if(hop){ window.location.href = hop + '?review=' + (step > 0 ? 'first' : 'last'); return; }
      reviewAnnounce(step > 0 ? '더 볼 변경점이 없습니다 — 마지막 장입니다.'
                              : '앞쪽에 더 볼 변경점이 없습니다 — 첫 장입니다.');
    });
    return;
  }
  var chosen = first ? reviewNavIndex                    // 첫 누름 = 지금 번호에 착지
                     : ((reviewNavIndex + step) % n + n) % n;   // 그 뒤부터 순환
  reviewNavIndex = chosen;
  syncReviewNavigation();
  var target = reviewShowPlanEntry(plan[chosen]);
  if(target) scrollReviewTargetIntoView(target);
}
function resetReviewNav(){
  var plan = reviewPlan();
  if(!plan.length) return;                    // 변경점 0건이면 묶음이 통째로 숨어 눌릴 일이 없다
  if(reviewNavLanded && reviewNavIndex === 0) return;   // 이미 첫 변경점에 서 있다(흐리게 보인다)
  reviewNavIndex = 0;
  reviewNavLanded = true;                     // 이 버튼을 누른 것 자체가 착지다
  syncReviewNavigation();                     // 숫자를 스크롤보다 **먼저** 갱신한다(2026-08-01 규칙)
  var target = reviewShowPlanEntry(plan[0]);  // 소유 페이지를 열고 스테퍼 카드까지 펼친 뒤
  if(target) scrollReviewTargetIntoView(target);
}
document.getElementById('reviewHome').addEventListener('click', resetReviewNav);
document.getElementById('reviewPrev').addEventListener('click', function(){ moveReviewTarget(-1); });
document.getElementById('reviewNext').addEventListener('click', function(){ moveReviewTarget(1); });
document.getElementById('reviewNav').addEventListener('keydown', function(e){
  if(e.key === 'ArrowLeft') moveReviewTarget(-1);
  if(e.key === 'ArrowRight') moveReviewTarget(1);
});
document.getElementById('reviewToggle').addEventListener('click', function(){
  reviewEnabled = !reviewEnabled;
  updateViewerSettings({reviewHighlights:reviewEnabled});
  syncReviewTools();
});
document.getElementById('reviewDrill').addEventListener('click', function(){
  reviewHideDrill = !reviewHideDrill;
  updateViewerSettings({reviewHideDrill:reviewHideDrill});
  reviewNavIndex = -1;          // 목록이 바뀐다 — 옛 인덱스는 다른 항목을 가리킨다
  reviewNavLanded = false;
  syncReviewTools();
});

var SCRIPT_TAIL_BASE = '[A-Za-z0-9\\u0370-\\u03FF\\u2113\\u2202\\u221E\\uD835]';
var SCRIPT_TAIL_MATH = new RegExp('(<\\/su[bp]>)(?=' + SCRIPT_TAIL_BASE + ')', 'g');
var SCRIPT_TAIL_SYM  = new RegExp('(<\\/su[bp]><\\/span>)(?=' + SCRIPT_TAIL_BASE + ')', 'g');
function scriptTailGap(t, re){
  return t.replace(re, '$1<span class="subgap"></span>');
}

function renderMath(raw){
  if(raw === null || raw === undefined) return '';
  var t = String(raw);
  t = t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  t = t.replace(/\\\(|\\\)/g, '');
  var blankIds = [];

  t = t.replace(/___([A-Z0-9_]+)___/g, function(m, id){
    blankIds.push(id);
    return 'XBLANKMARKERX' + (blankIds.length - 1) + 'XENDMARKERX';
  });

  t = t.replace(/\\begin\{vmatrix\}([\s\S]*?)\\end\{vmatrix\}/g, function(m, body){
    var rows = body.split(/\\\\/).map(function(r){ return r.trim(); })
                   .filter(function(r){ return r.length; });
    return '<span class="mat mat-v">' + rows.map(function(r){
      return '<span class="mat-row">' + r.split(/&amp;/).map(function(c){
        return '<span class="mat-cell">' + c.trim() + '</span>';
      }).join('') + '</span>';
    }).join('') + '</span>';
  });

  t = t.replace(/\\left\\\{/g, 'XLBRACEX').replace(/\\right\\\}/g, 'XRBRACEX');
  t = t.replace(/\\\{/g, 'XLBRACEX').replace(/\\\}/g, 'XRBRACEX');

  t = t.replace(/\{,\}/g, ',');
  t = t.replace(/\\mathrm\{([^{}]*)\}/g, '$1');
  t = t.replace(/\\text\{([^{}]*)\}/g, '$1');
  t = t.replace(/\\vec\{([^{}]*)\}/g, '<span class="vec">$1</span>');
  t = t.replace(/\\mathbf\{([^{}]*)\}/g, '<span class="vecb">$1</span>');
  t = t.replace(/\\mathcal\{V\}/g, '𝒱');
  t = t.replace(/\\mathsf\{([^{}]*)\}/g, '<span class="sansup">$1</span>');
  t = t.replace(/\\overline\{([^{}]*)\}/g, '<span class="ovl">$1</span>');
  t = t.replace(/\\hl\{([^{}]*)\}/g, '<span class="mathhl">$1</span>');
  var DOT_TALL_MACRO = /^\\(?:theta|beta|delta|zeta|lambda|xi|phi|psi|[A-Z])/;
  var DOT_TALL_CHAR = /^[A-Z0-9bdfhijkltΒΔΘΛΞΠΣΦΨΩβδζθλξφψ]/;
  function baseIsTall(base) {
    var b = String(base).replace(/<[^>]*>/g, '').trim();
    return b.charAt(0) === '\\' ? DOT_TALL_MACRO.test(b) : DOT_TALL_CHAR.test(b);
  }
  var blobTall = false;
  t.replace(/\\d?dot\{([^{}]*)\}/g, function (_m, b) {
    if (baseIsTall(b)) blobTall = true;
    return _m;
  });
  function dotClass(base) {
    return (blobTall || baseIsTall(base)) ? ' dot-tall' : '';
  }
  t = t.replace(/\\ddot\{([^{}]*)\}/g, function (_m, b) {
    var c = dotClass(b);
    return '<span class="dot"><span class="dot-mark dot-l' + c + '" aria-hidden="true"></span>'
      + '<span class="dot-mark dot-r' + c + '" aria-hidden="true"></span>' + b + '</span>';
  });
  t = t.replace(/\\dot\{([^{}]*)\}/g, function (_m, b) {
    return '<span class="dot"><span class="dot-mark' + dotClass(b) + '" aria-hidden="true"></span>'
      + b + '</span>';
  });
  t = t.replace(/\\sqrt\{([^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*)\}/g,
    '<span class="sqrt"><svg class="sqrt-sign" viewBox="0 0 20 100" preserveAspectRatio="none"'
    + ' aria-hidden="true" focusable="false"><path d="M0.5 58 L5 54 L11.5 97 L20 0"/></svg>'
    + '<span class="sqrt-body">$1</span></span>');
  t = t.replace(/\\int_([A-Za-z0-9])\^([A-Za-z0-9])/g, '\\int_{$1}^{$2}')
       .replace(/\\int_([A-Za-z0-9])\^\{/g, '\\int_{$1}^{').replace(/\\int_(\{[^{}]*\})\^([A-Za-z0-9])/g, '\\int_$1^{$2}');
  t = t.replace(/\\int_\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\^\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}[ ]?/g,
    '<span class="intop"><span class="bigop">∫</span><sub>$1</sub><sup>$2</sup></span>');
  t = t.replace(/<span class="intop"><span class="bigop">∫<\/span><sub>([0-9])<\/sub><sup>([0-9])<\/sup><\/span>/g,
    '<span class="intop intop-short"><span class="bigop">∫</span><sub>$1</sub><sup>$2</sup></span>');
  var supsubPrev, supsubPass = 0;
  do {
    supsubPrev = t;
    t = t.replace(/_\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/g, '<sub>$1</sub>');
    t = t.replace(/_\\([A-Za-z]+)/g, '<sub>\\$1</sub>');
    t = t.replace(/_([A-Za-z0-9])/g, '<sub>$1</sub>');
    t = t.replace(/\^\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/g, '<sup>$1</sup>');
    t = t.replace(/\^([A-Za-z0-9])/g, '<sup>$1</sup>');
    supsubPass += 1;
  } while (t !== supsubPrev && supsubPass < 4);
  t = t.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g,
    '<span class="frac"><span class="frac-num">$1</span><span class="frac-den">$2</span></span>⁣');

  t = t.replace(/\\(Delta|delta|Omega|omega|lambda|mu|nu|theta|alpha|beta|phi|psi|sigma|tau|varepsilon|gamma|rho|pi|eta|partial|infty|ell|prime|cdots|ldots)[ ]+(?=[A-Za-z0-9\\(<])/g, '\\$1{}');

  t = t.replace(/(\\(?:qquad|quad|,|;))[ ]+/g, '$1');

  var symbols = [
    [/\\Longrightarrow/g, '⟹'], [/\\Rightarrow/g, '⇒'],
    [/\\approx/g, '≈'],
    [/\\propto(?![A-Za-z])/g, '∝'],
    [/ *\\times(?![A-Za-z]) */g, "<span class='cdot'>×</span>"],
    [/\\cdots(?![A-Za-z])/g, '⋯'],
    [/ *\\cdot(?![A-Za-z]) */g, "<span class='cdot'>·</span>"],
    [/\\partial(?![A-Za-z])/g, '∂'], [/\\infty(?![A-Za-z])/g, '∞'],
    [/\\le(?![A-Za-z])/g, '≤'], [/\\ge(?![A-Za-z])/g, '≥'], [/\\ne(?![A-Za-z])/g, '≠'],
    [/\\to(?![A-Za-z])/g, '→'], [/\\mp(?![A-Za-z])/g, '∓'],
    [/\\ldots(?![A-Za-z])/g, '…'],
    [/\\kappa(?![A-Za-z])/g, 'κ'],
    [/\\lambda(?![A-Za-z])/g, 'λ'], [/\\mu(?![A-Za-z])/g, 'μ'],
    [/\\nu(?![A-Za-z])/g, 'ν'], [/\\omega(?![A-Za-z])/g, 'ω'],
    [/\\theta(?![A-Za-z])/g, 'θ'], [/\\alpha(?![A-Za-z])/g, 'α'],
    [/\\beta(?![A-Za-z])/g, 'β'], [/\\phi(?![A-Za-z])/g, 'φ'],
    [/\\psi(?![A-Za-z])/g, 'ψ'], [/\\sigma(?![A-Za-z])/g, 'σ'],
    [/\\tau(?![A-Za-z])/g, 'τ'], [/\\varepsilon(?![A-Za-z])/g, 'ε'],
    [/\\ell(?![A-Za-z])/g, 'ℓ'],
    [/\\delta(?![A-Za-z])/g, 'δ'],
    [/\\arctan(?![A-Za-z])/g, 'arctan'], [/\\arcsin(?![A-Za-z])/g, 'arcsin'],
    [/\\arccos(?![A-Za-z])/g, 'arccos'],
    [/\\sinh(?![A-Za-z])/g, 'sinh'], [/\\cosh(?![A-Za-z])/g, 'cosh'],
    [/\\tanh(?![A-Za-z])/g, 'tanh'],
    [/\\sec(?![A-Za-z])/g, 'sec'], [/\\csc(?![A-Za-z])/g, 'csc'],
    [/\\cot(?![A-Za-z])/g, 'cot'], [/\\log(?![A-Za-z])/g, 'log'],
    [/\\lim(?![A-Za-z])/g, 'lim'],
    [/\\min(?![A-Za-z])/g, 'min'], [/\\max(?![A-Za-z])/g, 'max'],
    [/\\equiv(?![A-Za-z])/g, '≡'],
    [/\\sin(?![A-Za-z])/g, 'sin'], [/\\cos(?![A-Za-z])/g, 'cos'],
    [/\\tan(?![A-Za-z])/g, 'tan'], [/\\ln(?![A-Za-z])/g, 'ln'],
    [/\\exp(?![A-Za-z])/g, 'exp'], [/\\prime(?![A-Za-z])/g, '′'],
    [/\\gamma/g, 'γ'],
    [/\\pm/g, '±'], [/\\sum_i\s*/g, 'Σᵢ'], [/\\sum\s*/g, 'Σ'],
    [/\\oint\s*/g, '<span class="bigop">∮</span>'],
    [/\\int\s*/g, '<span class="bigop">∫</span>'],
    [/\\rho/g, 'ρ'], [/\\Delta/g, 'Δ'], [/\\pi/g, 'π'], [/\\eta/g, 'η'],
    [/\\Omega/g, 'Ω'],
    [/\\Gamma(?![A-Za-z])/g, 'Γ'],
    [/\\!/g, ''],
    [/ *\\, */g, ' '],
    [/\\left\\\|/g, '‖'], [/\\right\\\|/g, '‖'],
    [/\\qquad/g,' '], [/\\quad/g, ' '], [/\\,/g, ' '], [/\\;/g, ' '], [/\\ /g, ' '],
    [/\\left\(/g, '('], [/\\right\)/g, ')'],
    [/\\left\[/g, '['], [/\\right\]/g, ']'],
    [/\\left\|/g, '|'], [/\\right\|/g, '|'],
    [/\\\|/g, '‖']
  ];
  symbols.forEach(function(pair){ t = t.replace(pair[0], pair[1]); });
  t = t.replace(/([α-ωΑ-Ωϕϑε]) +(?=[A-Za-z])/g, '$1');

  t = t.replace(/[{}]/g, '');
  t = t.replace(/XLBRACEX/g, '{').replace(/XRBRACEX/g, '}');
  t = t.replace(/([A-Za-z0-9)\]}|]|<\/[a-z]+>)('+)(?=[(),_<|}])/g,
                function(m, head, marks){ return head + marks.replace(/'/g, '′'); });
  t = t.replace(/([A-Za-z0-9)\]}|]|<\/[a-z]+>)('+)(?=\s|$|[=+\-*/^])/g,
                function(m, head, marks){ return head + marks.replace(/'/g, '′') + ' '; });
  t = t.replace(/\n/g, '<br>');
  t = t.replace(/<br>(?=조건:|➜)/g, '<br><span class="soltpl-gap"></span>');

  t = t.replace(/XBLANKMARKERX(\d+)XENDMARKERX/g, function(m, idx){
    var id = blankIds[Number(idx)];
    return '<button class="blankbtn" data-blank-id="' + id + '" onclick="openBlank(this,\'' + id + '\')" title="정답 보기">___</button>';
  });

  t = scriptTailGap(t, SCRIPT_TAIL_MATH);
  t = t.replace(/⁣[  ]?/g, '');
  var nbarOpen = true;
  t = t.replace(/‖/g, function(){
    var cls = nbarOpen ? 'nbar nbar-open' : 'nbar nbar-close';
    nbarOpen = !nbarOpen;
    return '<span class="' + cls + '">‖</span>';
  });
  t = t.replace(/ℓ/g, '<span class="ell">ℓ</span>');
  var operandBefore = false;
  return t.split(/(<[^>]*>)/g).map(function(part){
    if(part.charAt(0) === '<'){
      if(/^<(?:sub|sup)>/.test(part) || /class="frac-(?:num|den)"/.test(part)) operandBefore = false;
      if(/^<\/(?:sub|sup)>/.test(part)) operandBefore = true;
      return part;
    }
    var end = 0;
    function endsOperand(text){ return /[A-Za-z0-9\u0370-\u03ff)\]}]$/.test(text.trim()); }
    var result = part.replace(/[ \t\u00a0]*(&lt;=|&gt;=|&lt;|&gt;|[=≈≠≤≥+−±-])[ \t\u00a0]*/g,
      function(match, op, at){
        var before = part.slice(end, at);
        if(before.trim()) operandBefore = endsOperand(before);
        var binary = /^[+−±-]$/.test(op), spaced = !binary || operandBefore;
        operandBefore = false; end = at + match.length;
        return spaced ? '<span class="math-' + (binary ? 'binary' : 'relation') + '">' + op + '</span>' : op;
      });
    if(part.slice(end).trim()) operandBefore = endsOperand(part.slice(end));
    return result;
  }).join('');
}

function fmtOne(raw){
  var mathSpans = [];
  var source = raw === null || raw === undefined ? '' : String(raw);
  source = source.replace(/\\\((.+?)\\\)/g, function(_, math){
    mathSpans.push(math);
    return '\uE000' + (mathSpans.length - 1) + '\uE001';
  });
  var t = esc(source);
  t = t.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  t = t.replace(/\[\[(?:([^@\[\]]+)@)?(ch\d{2}):([A-Za-z0-9_-]+)(?:\/([A-Za-z0-9_-]+))?\|([^\]]+)\]\]/g,
    function(_, subjectFolder, chapter, target, child, label){
      var fragment = target.indexOf('fig-') === 0 ? target :
        (target.indexOf('f-') === 0 && !child ? 'formula-' + target :
          (child ? target + '-' + child : 'theory-' + target));
      if(!subjectFolder){
        return '<a class="xlink" href="' + chapter + '.html#' + fragment + '">' + label + '</a>';
      }
      var host = location.hostname;
      var isLocal = host === 'localhost' || host === '127.0.0.1';
      var port = isLocal ? LOCAL_PORTS[subjectFolder] : null;
      var href = port
        ? location.protocol + '//' + host + ':' + port + '/'
          + encodeURIComponent(subjectFolder) + '/' + chapter + '.html#' + fragment
        : '../' + encodeURIComponent(subjectFolder) + '/' + chapter + '.html#' + fragment;
      return '<a class="xlink xlink-cross" href="' + href + '">' + label + '</a>';
    });
  t = t.replace(/([Δ∆]?[A-Za-zα-ωΑ-Ω])_\{([A-Za-z0-9α-ωΑ-Ω]+(?:[,.][A-Za-z0-9α-ωΑ-Ω]+)*)\}/g, '<span class="sym">$1<sub>$2</sub></span>');
  t = t.replace(/([Δ∆]?[A-Za-zα-ωΑ-Ω])_([A-Za-z0-9α-ωΑ-Ω]+(?:,[a-z]+)*)/g, '<span class="sym">$1<sub>$2</sub></span>');
  t = scriptTailGap(t, SCRIPT_TAIL_SYM);
  t = t.replace(/\uE000(\d+)\uE001/g, function(_, idx){
    return '<span class="imath">' + renderMath(mathSpans[Number(idx)]) + '</span>';
  });
  return t;
}
function fmtTable(lines, cls){
  var cells = function(l){
    return l.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(function(c){ return c.trim(); });
  };
  var head = cells(lines[0]);
  var body = lines.slice(2).map(cells);
  return '<table class="tbl' + (cls || '') + '"><thead><tr>' +
    head.map(function(c){ return '<th>' + fmtOne(c) + '</th>'; }).join('') +
    '</tr></thead><tbody>' +
    body.map(function(r){
      return '<tr>' + r.map(function(c){ return '<td>' + fmtOne(c) + '</td>'; }).join('') + '</tr>';
    }).join('') + '</tbody></table>';
}
function fmtBlock(raw, cls){
  var lines = String(raw).split('\n').filter(function(l){ return l.trim() !== ''; });
  var isTable = lines.length > 2 &&
    lines.every(function(l){ return /^\s*\|.*\|\s*$/.test(l); }) &&
    /^\s*\|[\s:|-]+\|\s*$/.test(lines[1]);
  if(isTable) return fmtTable(lines, cls);
  var isList = lines.length > 1 && lines.every(function(l){ return /^\s*-\s+/.test(l); });
  if(isList) return '<ul class="tlist' + (cls || '') + '">' + lines.map(function(l){
    return '<li>' + fmtOne(l.replace(/^\s*-\s+/, '')) + '</li>';
  }).join('') + '</ul>';
  var isOList = lines.length > 1 && lines.every(function(l){ return /^\s*\d+\.\s+/.test(l); });
  if(isOList) return '<ol class="tlist' + (cls || '') + '">' + lines.map(function(l){
    return '<li>' + fmtOne(l.replace(/^\s*\d+\.\s+/, '')) + '</li>';
  }).join('') + '</ol>';
  var isMath = lines.length > 0 && lines.every(function(l){ return /^\s*\\\(.*\\\)\s*$/.test(l); });
  if(isMath) return '<div class="fmath mono' + (cls || '') + '">' + lines.map(function(l){
    return '<div class="fmath-line">' + renderMath(l.trim().replace(/^\\\(/, '').replace(/\\\)$/, '')) + '</div>';
  }).join('') + '</div>';
  return '<p' + (cls ? ' class="' + String(cls).replace(/^\s+/, '') + '"' : '') + '>' + fmtOne(raw) + '</p>';
}
function fmtText(raw){
  if(raw === null || raw === undefined) return '';
  var parts = String(raw).split(/\n{2,}/);
  if(parts.length === 1 && !/^\s*-\s+/.test(parts[0])) return fmtOne(parts[0]);
  return parts.map(function(p){ return fmtBlock(p); }).join('');
}

function openBlank(btn, id){
  var scope = btn.closest('#pracCard, #exampleCard') || document;
  var el = scope.querySelector('[id="ans-' + id + '"], [id="ex-ans-' + id + '"]');
  if(!el) return;
  el.open = !el.open;
}

var kindLabel = {
  comparative:'차이 비교',
  derivational:'식이 나오는 과정',
  sequential:'시간에 따른 변화'
};
function revealBar(d){
  if(!d.revealMode) return '';
  return '<div class="fig-reveal-bar">' +
    '<span>문제를 먼저 읽고 누르세요</span>' +
    '<button class="fig-reveal-btn" data-reveal-all="' + esc(d.id) + '">조건 수치 보기</button></div>';
}

function diagramNote(d, owner){
  return reviewNoteText(d) ? reviewNote(d) : reviewNote(owner);
}
function glossedPrompt(item){
  var text = String((item && item.prompt) || '');
  ((item && item.glossary) || []).forEach(function(g){
    if(!g || !g.term || !g.ko) return;
    var word = String(g.term).replace(/[.*+?^$(){}|[\]\\]/g, '\\$&');
    var re = new RegExp('(^|[^A-Za-z])(' + word + ')(?![A-Za-z])', 'i');
    text = text.replace(re, function(m, pre, hit){ return pre + hit + '(' + g.ko + ')'; });
  });
  return text;
}
function displayMathZero(svg){
  return String(svg || '');
}
function renderDiagrams(diagrams, owner){
  if(arguments.length < 2) console.error('renderDiagrams: 주인(owner) 인자가 빠졌다 — 그 자리 삽화만 사유가 빈손이 된다');
  if(!diagrams || !diagrams.length) return '';
  return diagrams.map(function(d){
    return '<div id="' + esc(d.id) + '" class="diagram-box' + (d.verticalPadding === 'compact' ? ' diagram-compact' : '') + (d._reviewChanged ? ' review-diagram' + reviewLevelClass(d._reviewChangeLevel) : '') + '"' +
      (d.revealMode ? ' data-reveal-mode="' + esc(d.revealMode) + '"' : '') + (d._reviewChanged ? diagramNote(d, owner) : '') + '>' +
      (d._reviewChanged ? '<span class="review-badge">' + (d._reviewChangeLevel === 'minor' ? '일부 수정' : '전면 수정') + '</span>' : '') +
      (kindLabel[d.kind] ? '<div class="diagram-kind">' + esc(kindLabel[d.kind]) + '</div>' : '') +
      displayMathZero(d.svg) +
      revealBar(d) +
      motionBar(d) +
      spotlightBar(d) +
    '</div>';
  }).join('');
}

var SPOTLIGHT_BY_FIG = {};
var SPOTLIGHT_DIM = 0.22;   // 흐린 대상의 불투명도 — 윤곽은 남고 색은 물러나는 값(렌더에서 고름)
function spotlightOn(){ return !!viewerSettings.spotSlideMode; }
function spotlightBar(d){
  var s = d && d.spotlight;
  if(!s || !s.length) return '';
  var spec = SPOTLIGHT_BY_FIG[d.id] = {steps: s, at: 0};
  var parts = d._spotHtml || [];
  var body = parts.some(Boolean) ? '<div class="spot-body">' + s.map(function(st, k){
    return parts[k] ? '<div class="spot-step" data-step="' + k + '">' + parts[k] + '</div>' : '';
  }).join('') + '</div>' : '';
  setTimeout(function(){ var box = document.getElementById(d.id); if(box) applySpotlight(box, spec); }, 0);
  return body + '<div class="spot-bar" data-spot="' + esc(d.id) + '">' +
    '<button type="button" class="tool-toggle spot-toggle" data-setting-keys="spotSlideMode">슬라이드: 켜짐</button>' +
    '<span class="spot-caption"></span>' +
    '<span class="spot-nav">' +
      '<button type="button" class="motion-play spot-btn" data-dir="-1">← 이전</button>' +
      '<button type="button" class="motion-play spot-btn" data-dir="1">다음 →</button>' +
    '</span>' +
  '</div>';
}
function applySpotlight(box, spec){
  var ids = [];
  spec.steps.forEach(function(st){ (st.focus || []).forEach(function(g){ if(ids.indexOf(g) === -1) ids.push(g); }); });
  var on = spotlightOn();
  var cur = on ? spec.steps[spec.at] : null;
  var toggle = box.querySelector('.spot-toggle');
  if(toggle) toggle.textContent = '슬라이드: ' + (on ? '켜짐' : '꺼짐');
  var nav = box.querySelector('.spot-nav');
  if(nav) nav.hidden = !on;
  ids.forEach(function(gid){
    var el = box.querySelector('svg [id="' + String(gid).replace(/"/g, '\\"') + '"]');
    if(!el){ console.warn('[짚어 보기] 삽화에서 그룹을 못 찾았다 — ' + gid); return; }
    el.style.opacity = (!cur || (cur.focus || []).indexOf(gid) !== -1) ? '' : String(SPOTLIGHT_DIM);
  });
  box.querySelectorAll('svg .spot-overview').forEach(function(el){ el.style.display = cur ? 'none' : ''; });
  box.querySelectorAll('.spot-step').forEach(function(el){
    el.hidden = !!cur && Number(el.getAttribute('data-step')) !== spec.at;
  });
  var cap = box.querySelector('.spot-caption');
  if(cap) cap.textContent = cur ? (spec.at + 1) + ' / ' + spec.steps.length + ' · ' + (cur.caption || '')
                                : '전체 보기';
  box.querySelectorAll('.spot-btn').forEach(function(b){
    b.disabled = Number(b.getAttribute('data-dir')) < 0 ? spec.at <= 0 : spec.at >= spec.steps.length - 1;
  });
}
document.addEventListener('click', function(e){
  var t = e.target.closest && e.target.closest('.spot-btn, .spot-toggle');
  if(!t || t.disabled) return;
  var bar = t.closest('.spot-bar');
  var spec = bar && SPOTLIGHT_BY_FIG[bar.getAttribute('data-spot')];
  if(!spec) return;
  if(t.classList.contains('spot-toggle')){
    updateViewerSettings({spotSlideMode: !viewerSettings.spotSlideMode});
    Object.keys(SPOTLIGHT_BY_FIG).forEach(function(id){
      var box = document.getElementById(id);
      if(box) applySpotlight(box, SPOTLIGHT_BY_FIG[id]);
    });
    return;
  }
  spec.at = Math.max(0, Math.min(spec.steps.length - 1, spec.at + Number(t.getAttribute('data-dir'))));
  applySpotlight(bar.closest('.diagram-box'), spec);
});

var MOTION_FRAME_MS = 250;   // 12프레임 상한에서 3초. 한 번 보고 따라갈 수 있는 길이다.
var MOTION_BY_FIG = {};
var MOTION_STATE_BY_FIG = {};

function motionBar(d){
  var m = d && d.motion;
  if(!m || !m.tracks || !m.tracks.length) return '';
  MOTION_BY_FIG[d.id] = m;
  return '<div class="motion-bar">' +
    '<span class="motion-caption">' + esc(m.caption || '') + '</span>' +
    '<span class="motion-status" aria-live="polite"></span>' +
    '<span class="motion-controls">' +
      '<button type="button" class="motion-step" data-motion-action="prev" aria-label="이전 단계">← 이전</button>' +
      '<button type="button" class="motion-play" data-motion-action="play">동작 보기</button>' +
      '<button type="button" class="motion-step" data-motion-action="next" aria-label="다음 단계">다음 →</button>' +
      '<button type="button" class="motion-reset" data-motion-action="reset">초기화</button>' +
    '</span>' +
  '</div>';
}

var MOTION_SPOT_DIM = 0.25, MOTION_SPOT_RAMP = 0.15;
var MOTION_MORPH_ATTRS = ['x1', 'y1', 'x2', 'y2', 'points'];
function motionTrackKeyframes(track, el){
  var from = Number(track.from), to = Number(track.to);
  if(track.attr === 'opacity') return [{opacity: from}, {opacity: to}];
  if(track.attr === 'rotate' && track.pivot){
    el.style.transformBox = 'view-box';
    el.style.transformOrigin = Number(track.pivot[0]) + 'px ' + Number(track.pivot[1]) + 'px';
    return [{transform: 'rotate(' + from + 'deg)'}, {transform: 'rotate(' + to + 'deg)'}];
  }
  if(track.attr === 'dx') return [{transform: 'translate(' + from + 'px,0)'},
                                  {transform: 'translate(' + to + 'px,0)'}];
  if(track.attr === 'dy') return [{transform: 'translate(0,' + from + 'px)'},
                                  {transform: 'translate(0,' + to + 'px)'}];
  if(track.attr === 'grow'){
    var len = el.getTotalLength ? el.getTotalLength() : 0;
    if(!len) return null;
    el.style.strokeDasharray = len;
    return [{strokeDashoffset: len * (1 - from)}, {strokeDashoffset: len * (1 - to)}];
  }
  return null;
}

function motionFrameCount(motion){
  return Math.max(2, Math.round(Number(motion.frames) || 2));
}
function totalMotionDuration(motion){
  return motionFrameCount(motion) * MOTION_FRAME_MS;
}
function motionBounds(track){
  var at = track.at || [0, 1];
  var a = Math.max(0, Math.min(1, Number(at[0])));
  return [a, Math.max(a, Math.min(1, Number(at[1])))];
}
function motionValue(track, progress){
  var bounds = motionBounds(track), a = bounds[0], b = bounds[1];
  var t = b === a ? (progress >= b ? 1 : 0) : Math.max(0, Math.min(1, (progress - a) / (b - a)));
  if(track.ease === 'easeInOut') t = t * t * (3 - 2 * t);
  return Number(track.from) + (Number(track.to) - Number(track.from)) * t;
}
function rememberMotionStyle(state, el){
  for(var i = 0; i < state.styles.length; i++) if(state.styles[i].el === el) return;
  var attrs = {};
  MOTION_MORPH_ATTRS.forEach(function(name){ attrs[name] = el.getAttribute(name); });
  state.styles.push({el: el, opacity: el.style.opacity, transform: el.style.transform,
                     transformBox: el.style.transformBox, transformOrigin: el.style.transformOrigin,
                     strokeDasharray: el.style.strokeDasharray, strokeDashoffset: el.style.strokeDashoffset,
                     attrs: attrs});
}
function restoreMotionStyles(state){
  state.styles.forEach(function(saved){
    saved.el.style.opacity = saved.opacity;
    saved.el.style.transform = saved.transform;
    saved.el.style.transformBox = saved.transformBox;
    saved.el.style.transformOrigin = saved.transformOrigin;
    saved.el.style.strokeDasharray = saved.strokeDasharray;
    saved.el.style.strokeDashoffset = saved.strokeDashoffset;
    MOTION_MORPH_ATTRS.forEach(function(name){
      var v = saved.attrs[name];
      if(v === null) saved.el.removeAttribute(name); else saved.el.setAttribute(name, v);
    });
  });
}
function motionTopLevel(state){
  var svg = state.box.querySelector('svg');
  return svg ? Array.prototype.slice.call(svg.children) : [];
}
function spotlightLevel(track, progress){
  var bounds = motionBounds(track), a = bounds[0], b = bounds[1];
  if(progress <= a || progress >= b) return 0;
  var ramp = MOTION_SPOT_RAMP * (b - a);
  return ramp > 0 ? Math.min(1, Math.min(progress - a, b - progress) / ramp) : 1;
}
function applyDrivenMotion(state, progress){
  var active = [], lit = {};
  (state.motion.tracks || []).forEach(function(track){
    if(!track || !track.at) return;
    if(track.attr === 'morph' && track.points_from && track.points_to){
      var el = state.box.querySelector('[id="' + track.target + '"]');
      var r = motionValue({at: track.at, ease: track.ease, from: 0, to: 1}, progress);
      var pts = track.points_from.map(function(p, i){
        var q = track.points_to[i] || p;
        return [Number(p[0]) + (Number(q[0]) - Number(p[0])) * r, Number(p[1]) + (Number(q[1]) - Number(p[1])) * r];
      });
      if(el && el.tagName.toLowerCase() === 'line' && pts.length === 2){
        el.setAttribute('x1', pts[0][0]); el.setAttribute('y1', pts[0][1]);
        el.setAttribute('x2', pts[1][0]); el.setAttribute('y2', pts[1][1]);
      } else if(el){
        el.setAttribute('points', pts.map(function(p){ return p[0] + ',' + p[1]; }).join(' '));
      }
    }
    if(track.spotlight && spotlightLevel(track, progress) > 0){
      active.push(track);
      track.spotlight.forEach(function(id){ lit[id] = true; });
    }
  });
  var level = 0;
  active.forEach(function(track){ level = Math.max(level, spotlightLevel(track, progress)); });
  var factor = 1 - (1 - MOTION_SPOT_DIM) * level;
  motionTopLevel(state).forEach(function(child){
    var keep = Object.keys(lit).some(function(id){
      return child.id === id || !!child.querySelector('[id="' + id + '"]');
    });
    if(keep || !active.length) return;
    var base = Number(child.getAttribute('opacity'));
    child.style.opacity = (isNaN(base) || child.getAttribute('opacity') === null ? 1 : base) * factor;
  });
}
function motionLoop(state, run){
  if(state.run !== run || !state.playing) return;
  var total = totalMotionDuration(state.motion);
  var progress = Math.min(1, (state.elapsed + Math.max(0, Date.now() - state.startedAt)) / total);
  applyDrivenMotion(state, progress);
  if(progress < 1) requestAnimationFrame(function(){ motionLoop(state, run); });
}
function motionState(box, motion){
  if(box._motionState) return box._motionState;
  var state = {box: box, motion: motion, frame: motionFrameCount(motion) - 1,
               animations: [], styles: [], playing: false, paused: false, timer: 0, run: 0,
               elapsed: 0, startedAt: 0};
  var spot = false;
  (motion.tracks || []).forEach(function(track){
    if(!track || !track.target) return;
    var el = box.querySelector('[id="' + track.target + '"]');
    if(el) rememberMotionStyle(state, el);
    if(track.spotlight) spot = true;
  });
  if(spot) motionTopLevel(state).forEach(function(child){ rememberMotionStyle(state, child); });
  box._motionState = state;
  MOTION_STATE_BY_FIG[box.id] = state;
  return state;
}
function motionBarFor(state){
  return state.box.querySelector('.motion-bar');
}
function syncMotionControls(state){
  var bar = motionBarFor(state);
  if(!bar) return;
  var count = motionFrameCount(state.motion), play = bar.querySelector('.motion-play');
  var prev = bar.querySelector('[data-motion-action="prev"]');
  var next = bar.querySelector('[data-motion-action="next"]');
  var reset = bar.querySelector('[data-motion-action="reset"]');
  var status = bar.querySelector('.motion-status');
  if(play) play.textContent = state.playing ? '일시정지' : (state.paused ? '계속 보기' : '동작 보기');
  if(prev) prev.disabled = state.playing || state.frame <= 0;
  if(next) next.disabled = state.playing || state.frame >= count - 1;
  if(reset) reset.disabled = !state.playing && !state.paused && state.frame <= 0;
  if(status) status.textContent = state.playing ? '재생 중' :
    (state.frame === 0 ? '시작 · 단계 1 / ' + count :
     (state.frame === count - 1 ? '완료 · 단계 ' + count + ' / ' + count :
      '단계 ' + (state.frame + 1) + ' / ' + count));
}
function cancelMotion(state){
  clearTimeout(state.timer);
  state.timer = 0;
  state.run += 1;
  state.animations.forEach(function(anim){ anim.cancel(); });
  state.animations = [];
  state.playing = false;
  state.paused = false;
  state.elapsed = 0;
  state.startedAt = 0;
}
function applyMotionFrame(state, frame){
  cancelMotion(state);
  var count = motionFrameCount(state.motion);
  state.frame = Math.max(0, Math.min(count - 1, frame));
  restoreMotionStyles(state);
  if(state.frame < count - 1){
    var progress = state.frame / (count - 1), moves = [];
    (state.motion.tracks || []).forEach(function(track){
      if(!track || !track.target || !track.at) return;
      var el = state.box.querySelector('[id="' + track.target + '"]');
      if(!el) return;
      var value = motionValue(track, progress);
      if(track.attr === 'opacity') el.style.opacity = value;
      if(track.attr === 'dx' || track.attr === 'dy' || track.attr === 'rotate'){
        var mv = null;
        moves.forEach(function(m){ if(m.el === el) mv = m; });
        if(!mv){ mv = {el: el, tx: 0, ty: 0, rot: null, pivot: null}; moves.push(mv); }
        if(track.attr === 'dx') mv.tx = value;
        if(track.attr === 'dy') mv.ty = value;
        if(track.attr === 'rotate'){ mv.rot = value; mv.pivot = track.pivot; }
      }
      if(track.attr === 'grow'){
        var len = el.getTotalLength ? el.getTotalLength() : 0;
        if(len){ el.style.strokeDasharray = len; el.style.strokeDashoffset = len * (1 - value); }
      }
    });
    moves.forEach(function(mv){
      var t = 'translate(' + mv.tx + 'px,' + mv.ty + 'px)';
      if(mv.rot !== null && mv.pivot){
        mv.el.style.transformBox = 'view-box';
        mv.el.style.transformOrigin = Number(mv.pivot[0]) + 'px ' + Number(mv.pivot[1]) + 'px';
        t += ' rotate(' + mv.rot + 'deg)';
      }
      mv.el.style.transform = t;
    });
    applyDrivenMotion(state, progress);
  }
  syncMotionControls(state);
}
function finishMotion(state, run){
  if(state.run !== run || state.paused) return;
  state.animations.forEach(function(anim){ anim.cancel(); });
  state.animations = [];
  state.playing = false;
  state.paused = false;
  state.elapsed = 0;
  state.startedAt = 0;
  state.frame = motionFrameCount(state.motion) - 1;
  restoreMotionStyles(state);
  syncMotionControls(state);
}
function startMotion(state){
  if(state.paused){
    state.paused = false;
    state.playing = true;
    state.animations.forEach(function(anim){ anim.play(); });
    state.startedAt = Date.now();
    state.timer = setTimeout(function(){ finishMotion(state, state.run); },
      Math.max(1, totalMotionDuration(state.motion) - state.elapsed) + 34);
    motionLoop(state, state.run);
    syncMotionControls(state);
    return;
  }
  applyMotionFrame(state, 0);
  var run = state.run, total = totalMotionDuration(state.motion);
  state.playing = true;
  state.elapsed = 0;
  state.startedAt = Date.now();
  var order = {dx: 0, dy: 0, rotate: 1};
  (state.motion.tracks || []).slice().sort(function(p, q){
    return (order[p && p.attr] || 0) - (order[q && q.attr] || 0);
  }).forEach(function(track){
    if(!track || !track.target || !track.at) return;
    var el = state.box.querySelector('[id="' + track.target + '"]');
    if(!el) return;
    var bounds = motionBounds(track), frames = motionTrackKeyframes(track, el);
    if(!frames) return;
    var isMove = track.attr === 'dx' || track.attr === 'dy' || track.attr === 'rotate';
    var anim = el.animate(frames, {duration: Math.max(1, (bounds[1] - bounds[0]) * total),
      delay: bounds[0] * total, fill: 'both', composite: isMove ? 'add' : 'replace',
      easing: track.ease === 'easeInOut' ? 'ease-in-out' : 'linear'});
    state.animations.push(anim);
  });
  state.timer = setTimeout(function(){ finishMotion(state, run); }, total + 34);
  motionLoop(state, run);
  syncMotionControls(state);
}
function pauseMotion(state){
  if(!state.playing) return;
  clearTimeout(state.timer);
  state.timer = 0;
  state.elapsed = Math.min(totalMotionDuration(state.motion),
    state.elapsed + Math.max(0, Date.now() - state.startedAt));
  state.startedAt = 0;
  state.animations.forEach(function(anim){ anim.pause(); });
  state.playing = false;
  state.paused = true;
  state.frame = Math.min(motionFrameCount(state.motion) - 1,
    Math.floor(state.elapsed / totalMotionDuration(state.motion) * (motionFrameCount(state.motion) - 1)));
  syncMotionControls(state);
}
function playMotion(box, motion){
  var state = motionState(box, motion);
  if(state.playing) pauseMotion(state);
  else startMotion(state);
}

document.addEventListener('click', function(ev){
  var btn = ev.target.closest && ev.target.closest('[data-motion-action]');
  if(!btn) return;
  var box = btn.closest('.diagram-box');
  if(!box || !box.id) return;
  var motion = MOTION_BY_FIG[box.id];
  if(!motion) return;
  var state = motionState(box, motion), action = btn.getAttribute('data-motion-action');
  if(action === 'play') playMotion(box, motion);
  if(action === 'prev') applyMotionFrame(state, state.frame - 1);
  if(action === 'next') applyMotionFrame(state, state.frame + 1);
  if(action === 'reset') applyMotionFrame(state, 0);
});

function paintGivenChips(scope){
  var boxes = (scope || document).querySelectorAll('.diagram-box svg');
  Array.prototype.forEach.call(boxes, function(svg){
    Array.prototype.forEach.call(svg.querySelectorAll('text[data-reveal]'), function(t){
      var prev = t.previousElementSibling;
      if(prev && prev.classList && prev.classList.contains('given-chip')) return;  // 이미 깔림
      var b;
      try { b = t.getBBox(); } catch(e) { return; }
      if(!b || b.width < 1 || b.height < 1) return;   // 숨은 페이지는 0 — 열릴 때 다시 깐다
      var r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      r.setAttribute('class', 'given-chip');
      r.setAttribute('data-reveal', t.getAttribute('data-reveal') || '1');
      r.setAttribute('x', (b.x - 4).toFixed(2));
      r.setAttribute('y', (b.y - 1.5).toFixed(2));
      r.setAttribute('width', (b.width + 8).toFixed(2));
      r.setAttribute('height', (b.height + 3).toFixed(2));
      r.setAttribute('rx', '3.5');
      if(t.classList.contains('shown')) r.classList.add('shown');
      t.parentNode.insertBefore(r, t);           // 글자 **앞**에 = 뒤에 깔린다
    });
  });
}
var chipPainting = false;
new MutationObserver(function(){
  if(chipPainting) return;                       // 칩을 넣는 것 자체가 DOM 변경이다(재귀 방지)
  chipPainting = true;
  try { paintGivenChips(document); } finally { chipPainting = false; }
}).observe(document.documentElement, {childList:true, subtree:true});

function revealConditionsIn(scope){
  if(!scope) return;
  Array.prototype.forEach.call(scope.querySelectorAll('.diagram-box[data-reveal-mode]'), function(box){
    Array.prototype.forEach.call(box.querySelectorAll('[data-reveal]'), function(n){ n.classList.add('shown'); });
    var btn = box.querySelector('.fig-reveal-btn');
    if(btn) btn.textContent = '조건 수치 숨기기';
  });
}

document.addEventListener('click', function(e){
  var t = e.target && e.target.closest ? e.target : null;
  if(!t) return;
  var all = t.closest('[data-reveal-all]');
  if(!all) return;
  var box = document.getElementById(all.getAttribute('data-reveal-all'));
  if(!box) return;
  var hidden = box.querySelectorAll('[data-reveal]:not(.shown)');
  if(hidden.length){
    Array.prototype.forEach.call(hidden, function(n){ n.classList.add('shown'); });
    all.textContent = '조건 수치 숨기기';
  } else {
    Array.prototype.forEach.call(box.querySelectorAll('[data-reveal]'), function(n){ n.classList.remove('shown'); });
    all.textContent = '조건 수치 보기';
  }
}, false);

var ccStageLabel = {recall:'떠올리기', explain:'설명하기', connect:'연결하기'};
var ccIdSeq = 0;
function renderComprehensionChecks(checks, owner){
  if(arguments.length < 2) console.error('renderComprehensionChecks: 주인(owner) 인자가 빠졌다 — 그 자리 체크만 사유가 빈손이 된다');
  if(!checks || !checks.length) return '';
  var items = checks.map(function(c){
    ccIdSeq += 1;
    var domId = 'cc-' + ccIdSeq;
    return '<details class="cc-item' + reviewClassOwned(c, 'item', owner) + '" id="' + domId + '">' +
      '<summary class="cc-head"><span class="cc-stage ' + esc(c.stage) + '">' + esc(ccStageLabel[c.stage] || c.stage) + '</span>' +
      '<span class="cc-q">' + fmtText(c.prompt) + '</span></summary>' +
      '<div class="cc-body">' +
        '<div class="cc-answer">' + fmtText(c.answer) + '</div>' +
        (c.explanation ? '<div class="cc-expl">' + fmtText(c.explanation) + '</div>' : '') +
        (c.followUp ? '<div class="cc-followup"><span class="cc-followup-tag">한 걸음 더</span>'
           + fmtText(c.followUp) + '</div>' : '') +
      '</div>' +
    '</details>';
  }).join('');
  return '<div class="cc-wrap">' + items + '</div>';
}

function renderPitfalls(pits, owner){
  if(arguments.length < 2) console.error('renderPitfalls: 주인(owner) 인자가 빠졌다 — 그 자리 함정만 사유가 빈손이 된다');
  if(!pits || !pits.length) return '';
  return '<div class="pitfall"><div class="pitfall-h">⚠ 여기서 잘 놓쳐요</div>' +
    pits.map(function(p){
      return '<div class="pitfall-item' + reviewClassOwned(p, 'item', owner) + '">' + fmtText(p.note) + '</div>';
    }).join('') +
  '</div>';
}

var sectionById = {};
CH.theory.sections.forEach(function(s){ sectionById[s.id] = s; });
var formulaIndexById = {};
CH.derivation.formulas.forEach(function(f, i){ formulaIndexById[f.id] = i; });
var derivTopicFirstIndex = {};
var derivTopics = [];
CH.derivation.formulas.forEach(function(f, i){
  if(derivTopicFirstIndex[f.topic] === undefined){
    derivTopicFirstIndex[f.topic] = i;
    derivTopics.push(f.topic);
  }
});


var jumpBackLabel = {recap:'자가점검', practice:'문제', example:'예제', derivation:'유도', formula:'공식', problems:'문제', textbook:'교재 문제', summary:'요약', theory:'이론', lo:'학습목표'};
function armJumpBack(fromPage){
  var btn = document.getElementById('jumpBack');
  btn.setAttribute('data-origin', fromPage);
  var lab = jumpBackLabel[fromPage] || '';
  var last = lab.charCodeAt(lab.length - 1);
  var batchim = last >= 0xAC00 && last <= 0xD7A3 && ((last - 0xAC00) % 28) !== 0;
  btn.textContent = '← ' + lab + (batchim ? '으로 돌아가기' : '로 돌아가기');
  btn.hidden = false;
}
document.getElementById('jumpBack').addEventListener('click', function(){
  this.hidden = true;
  if(this.getAttribute('data-origin') === '__cross-chapter'){ window.history.back(); return; }
  if(this.getAttribute('data-origin') === '__same-chapter'){
    if(samePageReturn){
      if(samePageReturn.page !== currentPage) showPage(samePageReturn.page);
      window.scrollTo(0, samePageReturn.y);
    }
    return;
  }
  showPage(this.getAttribute('data-origin') || 'recap');
});
var samePageReturn = null;
document.addEventListener('click', function(ev){
  var a = ev.target && ev.target.closest ? ev.target.closest('a.xlink') : null;
  if(!a) return;
  var url;
  try { url = new URL(a.getAttribute('href'), window.location.href); } catch(ignore) { return; }
  if(url.pathname !== window.location.pathname) return;   // 다른 장 — armCrossChapterBack 의 몫
  var target = url.hash ? document.getElementById(url.hash.slice(1)) : null;
  if(!target) return;                                     // 못 찾으면 브라우저에 맡긴다(빌드가 대상을 검사한다)
  ev.preventDefault();
  samePageReturn = {page: currentPage, y: window.scrollY};
  var host = target.closest('.page[data-page]');
  if(host && host.getAttribute('data-page') !== currentPage) showPage(host.getAttribute('data-page'));
  target.scrollIntoView({block:'start'});
  var btn = document.getElementById('jumpBack');
  btn.setAttribute('data-origin', '__same-chapter');
  btn.textContent = '← 보던 자리로 돌아가기';
  btn.hidden = false;
});
function armCrossChapterBack(){
  var ref = document.referrer;
  if(!ref) return;
  var url; try { url = new URL(ref); } catch(ignore) { return; }
  if(url.origin !== window.location.origin) return;
  var m = /ch(\d{2})\.html$/.exec(url.pathname);
  var here = /ch(\d{2})\.html$/.exec(window.location.pathname);
  if(!m || (here && m[1] === here[1])) return;
  var btn = document.getElementById('jumpBack');
  btn.setAttribute('data-origin', '__cross-chapter');
  btn.textContent = '← ' + parseInt(m[1], 10) + '장으로 돌아가기';
  btn.hidden = false;
}

document.getElementById('kwRow').innerHTML = (CH.keywords || []).map(function(kw){
  return '<span class="kw">' + fmtText(kw) + '</span>';
}).join('');

(function renderChapterIntro(){
  var el = document.getElementById('chIntro');
  var intro = CH.chapterIntro;
  if(!el || !intro) return;
  var rows = [
    ['이 장이 답하는 질문', intro.question],
    ['미리 알아야 할 것', intro.prerequisite],
    ['다음 장과의 연결', intro.nextLink]
  ].filter(function(r){ return r[1]; });
  if(!rows.length) return;
  el.innerHTML = (intro.summary ? '<p class="ch-intro-sum">' + fmtText(intro.summary) + '</p>' : '') +
    rows.map(function(r){
      return '<div class="ch-intro-row"><span class="ch-intro-k">' + esc(r[0]) + '</span>' +
             '<span class="ch-intro-v">' + fmtText(r[1]) + '</span></div>';
    }).join('');
  el.hidden = false;
})();

document.getElementById('loList').innerHTML = (CH.learningObjectives || []).map(function(lo, i){
  return '<li class="lo-item"><span class="lo-num">' + (i+1) + '</span><span class="lo-text">' + fmtText(lo.statement) + '</span></li>';
}).join('');

function renderReviewItem(ref, owner){
  var head = ref.linked === false
    ? ''
    : '<a class="review-prereq-link" href="' + esc(ref.href) + '">' +
        '<span>' + fmtText(ref.label) + '</span><span class="review-prereq-en">' + fmtText(ref.english) + '</span><span aria-hidden="true">→</span></a>';
  return '<div class="review-prereq-item">' + head + renderDiagrams(ref.diagrams, owner) + '</div>';
}
function renderReviewPrerequisites(refs, owner){
  if(!refs || !refs.length) return '';
  return '<div class="review-prereq"><div class="review-prereq-h">1장에서 먼저 복습</div>'
    + refs.map(function(ref){ return renderReviewItem(ref, owner); }).join('') + '</div>';
}
function theorySectionNo(id){
  for(var i = 0; i < CH.theory.sections.length; i++){
    if(CH.theory.sections[i].id === id) return i + 1;
  }
  return null;
}
function isChapterSummary(s){ return !!(s && s.chapterSummary); }
function theoryBodySections(){
  return CH.theory.sections.filter(function(s){ return !isChapterSummary(s); });
}
function summarySections(){ return CH.theory.sections.filter(isChapterSummary); }
function theoryHeadingHtml(s){
  var n = isChapterSummary(s) ? null : theorySectionNo(s.id);
  return (n ? n + '절 ' : '') + fmtText(s.heading);
}
function renderTheoryBody(s){
  var paras = String(s.content).split(/\n{2,}/);
  var byAnchor = {}, defByAnchor = {}, tail = [];
  (s.diagrams || []).forEach(function(dg){
    var a = dg.afterParagraph;
    if(a >= 1 && a <= paras.length){ (byAnchor[a] = byAnchor[a] || []).push(dg); }
    else { tail.push(dg); }
  });
  (s.definitions || []).forEach(function(def){
    var a = def.afterParagraph;
    if(a >= 1 && a <= paras.length){ (defByAnchor[a] = defByAnchor[a] || []).push(def); }
  });
  var reviewByAnchor = {}, reviewTop = [];
  (s.reviewPrerequisites || []).forEach(function(ref){
    var a = ref.afterParagraph;
    if(a >= 1 && a <= paras.length){ (reviewByAnchor[a] = reviewByAnchor[a] || []).push(ref); }
    else { reviewTop.push(ref); }
  });
  var html = renderReviewPrerequisites(reviewTop, s);
  var pieces = paras.map(function(p, i){
    var h = '';
    if(defByAnchor[i + 1]){
      h += defByAnchor[i + 1].map(function(def){
        return '<span class="def-anchor" id="' + esc(s.id + '-' + def.id) + '"></span>';
      }).join('');
    }
    h += fmtBlock(p, reviewParaClass(s, 'content', i));
    if(reviewByAnchor[i + 1]) h += '<div class="review-prereq review-prereq-inline">' + reviewByAnchor[i + 1].map(function(ref){ return renderReviewItem(ref, s); }).join('') + '</div>';
    return h;
  });
  var claimed = {};
  (s.diagrams || []).forEach(function(dg){
    if(!dg.spotlight) return;
    dg._spotHtml = [];
    dg.spotlight.forEach(function(st, k){
      (st._paragraphs || []).forEach(function(n){
        if(n < 1 || n > paras.length || claimed[n]) return;
        claimed[n] = true;
        dg._spotHtml[k] = (dg._spotHtml[k] || '') + pieces[n - 1] + (byAnchor[n] ? renderDiagrams(byAnchor[n], s) : '');
      });
    });
  });
  paras.forEach(function(p, i){
    if(claimed[i + 1]) return;
    html += pieces[i];
    if(byAnchor[i + 1]) html += renderDiagrams(byAnchor[i + 1], s);
  });
  return html + renderDiagrams(tail, s);
}
function theoryItemHtml(s){
  var tag = s.processType ? ('<span class="ptag">' + esc(s.processType) + '</span>') : '';
  var sourceRef = '';
  return '<div class="theory-item" id="theory-' + esc(s.id) + '" data-sec="' + esc(s.id) + '"><div class="theory-h">' + theoryHeadingHtml(s) + tag + '</div><div class="theory-c' + reviewClass(s, 'content') + '">' + renderTheoryBody(s) + '</div>' +
    sourceRef +
    '<div class="' + reviewClass(s, 'pitfalls').trim() + '">' + renderPitfalls(s.pitfalls, s) + '</div>' +
    '<div class="' + reviewClass(s, 'comprehensionChecks').trim() + '">'
      + renderComprehensionChecks(s.comprehensionChecks || [], s)
      + '</div></div>';
}
document.getElementById('theoryList').innerHTML = theoryBodySections().map(theoryItemHtml).join('');
document.getElementById('summaryList').innerHTML = summarySections().map(theoryItemHtml).join('');

var PROGRESS_KEY = 'progress:' + chapterStoragePrefix;
function progressSections(){ return theoryBodySections(); }
function progressLimitStored(){
  var n = progressSections().length, raw = null;
  if(Number(CH.chapterNumber) === 0) return n;
  try { raw = localStorage.getItem(PROGRESS_KEY); } catch(ignore) {}
  var v = parseInt(raw, 10);
  return (v >= 1 && v <= n) ? v : n;        // 값이 없거나 절 수가 바뀌었으면 «전체»
}
var progressLimit = progressLimitStored();
function progressIsFull(){ return progressLimit >= progressSections().length; }
function sectionInRange(id){
  var secs = progressSections();
  for(var i = 0; i < secs.length; i++){ if(secs[i].id === id) return i < progressLimit; }
  return true;                               // 이론 절에 없는 id(요약 등)는 자가 안 본다
}
function itemInRange(item){
  if(!item) return true;
  if(!item.section) return progressIsFull();
  return sectionInRange(item.section);
}
var formulaSectionIdx = (function(){
  var order = {}, map = {};
  progressSections().forEach(function(s, i){ order[s.id] = i; });
  (CH.practice || []).concat(CH.problems || []).forEach(function(it){
    if(!it || !it.section || !Object.prototype.hasOwnProperty.call(order, it.section)) return;
    (it.relatedFormulas || []).forEach(function(fid){
      if(!Object.prototype.hasOwnProperty.call(map, fid) || order[it.section] < map[fid]) map[fid] = order[it.section];
    });
  });
  var fromLo = {};
  (CH.learningObjectives || []).forEach(function(lo){
    var idx = (lo.relatedSections || []).filter(function(sid){
      return Object.prototype.hasOwnProperty.call(order, sid);
    }).map(function(sid){ return order[sid]; });
    if(!idx.length) return;
    var first = Math.min.apply(null, idx);
    (lo.relatedFormulas || []).forEach(function(fid){
      if(!Object.prototype.hasOwnProperty.call(fromLo, fid) || first < fromLo[fid]) fromLo[fid] = first;
    });
  });
  Object.keys(fromLo).forEach(function(fid){
    if(!Object.prototype.hasOwnProperty.call(map, fid)) map[fid] = fromLo[fid];
  });
  return map;
})();
function formulaInRange(f){
  if(!f || !Object.prototype.hasOwnProperty.call(formulaSectionIdx, f.id)) return true;
  return formulaSectionIdx[f.id] < progressLimit;
}
function renderProgressBar(){
  var bar = document.getElementById('progressBar');
  if(!bar) return;
  var secs = progressSections();
  if(secs.length < 2 || Number(CH.chapterNumber) === 0){ bar.hidden = true; return; }   // 절이 하나면 조절할 것이 없고, 0장은 늘 전체다
  bar.hidden = false;
  var sel = document.getElementById('progressSelect');
  sel.innerHTML = secs.map(function(s, i){
    var name = String(s.heading || '').replace(/\\[()\[\]]/g, '').replace(/\*\*/g, '');
    return '<option value="' + (i + 1) + '">' + (i + 1) + '절까지 · ' + esc(name)
      + (i === secs.length - 1 ? ' (전체)' : '') + '</option>';
  }).join('');
  sel.value = String(progressLimit);
}
function applyProgress(resetIndex){
  document.querySelectorAll('#theoryList .theory-item[data-sec]').forEach(function(el){
    var inRange = sectionInRange(el.getAttribute('data-sec'));
    el.classList.toggle('out-of-range', !inRange);
    if(inRange) el.classList.remove('peek');
  });
  renderProgressBar();
  if(resetIndex !== false){ exampleIndex = 0; pracIndex = 0; }
  renderExampleCard(); renderPracCard(); renderProblems(); renderDerivCard();
  if(typeof renderTextbook === 'function') renderTextbook();
  syncTheoryNext();
}
function setProgress(v){
  var n = progressSections().length;
  progressLimit = Math.max(1, Math.min(n, v));
  try { localStorage.setItem(PROGRESS_KEY, String(progressLimit)); } catch(ignore) {}
  applyProgress();
}
document.getElementById('progressSelect').addEventListener('change', function(){
  setProgress(parseInt(this.value, 10));
});
document.getElementById('theoryList').addEventListener('click', function(e){
  var head = e.target.closest('.theory-h');
  if(!head) return;
  var item = head.parentElement;
  if(item && item.classList.contains('out-of-range')) item.classList.toggle('peek');
});
document.getElementById('derivCard').addEventListener('click', function(e){
  var name = e.target.closest('.fcard-name');
  if(!name) return;
  var card = name.parentElement;
  if(card && card.classList.contains('out-of-range')) card.classList.toggle('peek');
});

var activeTheoryId = null;
function setTheoryTocActive(sectionId){
  activeTheoryId = sectionId;
  document.querySelectorAll('.theory-toc-link').forEach(function(link){
    link.classList.toggle('current', link.getAttribute('data-sec') === sectionId);
  });
}
function renderTheoryToc(){
  var secs = theoryBodySections();
  document.getElementById('theoryTocList').innerHTML = secs.map(function(s){
    return '<button class="theory-toc-link" data-sec="' + esc(s.id) + '">' + theoryHeadingHtml(s) + '</button>';
  }).join('');
  if(secs.length) setTheoryTocActive(secs[0].id);
}
function setTheoryTocOpen(open){
  document.getElementById('theoryToc').classList.toggle('open', open);
  document.getElementById('tocTrigger').setAttribute('aria-expanded', String(open));
  document.getElementById('tocScrim').classList.toggle('open', open);
}
function setDerivTocOpen(open){
  document.getElementById('derivToc').classList.toggle('open', open);
  document.getElementById('derivTocTrigger').setAttribute('aria-expanded', String(open));
  document.getElementById('tocScrim').classList.toggle('open', open);
}
function theoryTocBaseline(){
  var top = reviewBarOffset();                       // 읽기 영역의 시작(탭바 아래)
  return top + Math.max(0, window.innerHeight - top) / 2;
}
function syncTheoryTocFromScroll(){
  if(currentPage !== 'theory') return;
  var items = document.querySelectorAll('#theoryList .theory-item');
  if(!items.length) return;
  var line = theoryTocBaseline(), best = null;
  items.forEach(function(item){
    if(item.getBoundingClientRect().top <= line) best = item;
  });
  if(window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2){
    items.forEach(function(item){
      if(item.getBoundingClientRect().top < window.innerHeight) best = item;
    });
  }
  setTheoryTocActive((best || items[0]).id.replace('theory-', ''));
}
renderTheoryToc();
document.getElementById('theoryTocList').addEventListener('click', function(e){
  var link = e.target.closest('.theory-toc-link');
  if(!link) return;
  gotoSection(link.getAttribute('data-sec'));
  setTheoryTocOpen(false);
});
document.getElementById('tocTrigger').addEventListener('click', function(){
  setTheoryTocOpen(!document.getElementById('theoryToc').classList.contains('open'));
});
document.getElementById('tocScrim').addEventListener('click', function(){ setTheoryTocOpen(false); setDerivTocOpen(false); });
window.addEventListener('scroll', syncTheoryTocFromScroll, {passive:true});

function setDerivTocActive(topic){
  document.querySelectorAll('.deriv-toc-link').forEach(function(link){
    link.classList.toggle('current', link.getAttribute('data-topic') === topic);
  });
}
function renderDerivToc(){
  document.getElementById('derivTocList').innerHTML = derivTopics.map(function(topic){
    return '<button class="deriv-toc-link" data-topic="' + esc(topic) + '">' + esc(topic) + '</button>';
  }).join('');
}
renderDerivToc();
document.getElementById('derivTocList').addEventListener('click', function(e){
  var link = e.target.closest('.deriv-toc-link');
  if(!link) return;
  derivIndex = derivTopicFirstIndex[link.getAttribute('data-topic')];
  renderDerivCard();
  scrollCardToReadingPosition(document.querySelector('#derivCard .fcard'));
  setDerivTocOpen(false);
});
document.getElementById('derivTocTrigger').addEventListener('click', function(){
  setDerivTocOpen(!document.getElementById('derivToc').classList.contains('open'));
});

document.getElementById('recapList').innerHTML = (CH.learningObjectives || []).map(function(lo, i){
  var q = lo.statement.replace(/할 수 있다\.?$/, '할 수 있나요?');
  var links = '';
  (lo.relatedSections || []).forEach(function(sid){
    var s = sectionById[sid];
    if(s) links += '<button class="recap-link" data-sec="' + esc(sid) + '">' + esc(CH.theoryLabel || '이론') + ' · ' + theoryHeadingHtml(s) + '</button>';
  });
  (lo.relatedFormulas || []).forEach(function(fid){
    var idx = formulaIndexById[fid];
    if(idx !== undefined) links += '<button class="recap-link" data-fid="' + esc(fid) + '">공식 · ' + fmtText(CH.derivation.formulas[idx].name) + '</button>';
  });
  return '<div class="recap-item">' +
    '<div class="recap-q">' + (i+1) + '. ' + fmtText(q) + '</div>' +
    '<div class="recap-toggle">' +
      '<button class="recap-btn" data-lo="' + lo.id + '" data-val="yes">네, 설명할 수 있어요</button>' +
      '<button class="recap-btn" data-lo="' + lo.id + '" data-val="no">아직 헷갈려요</button>' +
    '</div>' +
    '<div class="recap-links" hidden><span>다시 보기 →</span>' + links + '</div>' +
  '</div>';
}).join('');
(function(){
  var rs = CH.reviewSet, box = document.getElementById('reviewSetBox');
  if(!rs || !box) return;
  var rows = (CH.learningObjectives || []).map(function(lo, i){
    var nums = (rs.byObjective || {})[lo.id] || [];
    if(!nums.length) return '';
    return '<div class="review-set-row"><b>목표 ' + (i+1) + '</b>' + esc(nums.join(', ')) + '</div>';
  }).join('');
  var ex = (rs.excluded || []).map(function(e){ return esc(e.num) + '(' + esc(e.why) + ')'; }).join(', ');
  box.innerHTML = '<div class="recap-q">반복용 — ' + esc(rs.label) + ' ' + rs.total + '문항</div>' +
    '<div class="review-set-row">위 교재 문제와 이 장의 문항은 목표마다 한 번씩 연습시킵니다. 시험 전에 반복하려면 교재 장 끝의 아래 번호를 푸세요(목표 번호는 학습목표 탭 번호).</div>' +
    rows + (ex ? '<div class="review-set-row">빼 둔 것: ' + ex + '</div>' : '');
  box.hidden = false;
})();
var recapPicks = chapterLearning.recapPicks && typeof chapterLearning.recapPicks === 'object'
  ? chapterLearning.recapPicks : {};  // loId -> 'yes' | 'no'
function syncRecapPicks(){
  document.querySelectorAll('#recapList .recap-item').forEach(function(item){
    var yesBtn = item.querySelector('.recap-btn[data-val="yes"]');
    var noBtn = item.querySelector('.recap-btn[data-val="no"]');
    if(!yesBtn || !noBtn) return;
    var pick = recapPicks[yesBtn.getAttribute('data-lo')];
    yesBtn.classList.toggle('picked-yes', pick === 'yes');
    noBtn.classList.toggle('picked-no', pick === 'no');
    var linksEl = item.querySelector('.recap-links');
    if(linksEl) linksEl.hidden = pick !== 'no';
  });
}
function updateRecapStatus(){
  var los = CH.learningObjectives || [];
  var yes = 0, no = 0;
  los.forEach(function(lo){
    if(recapPicks[lo.id] === 'yes') yes += 1;
    else if(recapPicks[lo.id] === 'no') no += 1;
  });
  var html = '<div class="recap-status">' +
    '<span>점검 <b>' + (yes + no) + '</b> / ' + los.length + '</span>' +
    '<span>설명 가능 <b>' + yes + '</b></span>' +
    '<span>아직 헷갈림 <b>' + no + '</b></span>' +
  '</div>';
  if(los.length && yes === los.length){
    var currentChapterIndex = SUBJECT_NAV.findIndex(function(ch){ return ch.number === Number(CH.chapterNumber); });
    var nextChapter = currentChapterIndex >= 0 ? SUBJECT_NAV[currentChapterIndex + 1] : null;
    var nextChapterAction = nextChapter
      ? '<a class="navbtn" href="' + esc(nextChapter.href) + '?start=lo">다음 챕터로 가기 →</a>'
      : '';
    var hasProblems = (CH.problems || []).length > 0 && hiddenPages.indexOf('problems') === -1;
    var problemsHidden = !hasProblems && (CH.problems || []).length > 0;
    var goNext = nextChapter ? ' – 바로 다음 장으로 넘어가세요.' : ' – 여기가 이 과목의 마지막 장입니다. 수고하셨습니다.';
    var reviewLine = hasProblems
      ? '기억을 굳히려면 며칠 뒤 문제 탭을 섞어서 다시 풀어보세요.'
      : problemsHidden
        ? '이 장의 문제 탭은 지금 감춰 두었습니다' + goNext
        : (Number(CH.chapterNumber) === 0 || CH.theoryLabel === '정리')
          ? '이 장은 ' + (Number(CH.chapterNumber) === 0 ? '지도' : '정리') + ' 역할이라 문제가 없습니다' + goNext
          : '이 장에는 아직 문제가 없습니다' + goNext;
    var shuffleAction = hasProblems
      ? '<button class="navbtn primary" id="recapShuffleBtn">지금 섞어서 다시 풀기 →</button>'
      : '';
    html += '<div class="recap-done">학습목표 ' + los.length + '개를 전부 스스로 설명할 수 있습니다 – 챕터 점검 완료!<br>' +
      reviewLine +
      '<div class="recap-actions">' + shuffleAction +
      nextChapterAction + '</div></div>';
  }
  document.getElementById('recapStatus').innerHTML = html;
  var b = document.getElementById('recapShuffleBtn');
  if(b) b.addEventListener('click', function(){
    shuffleOn = true;
    probOrder = fisherYates((CH.problems || []).length);
    wrongOnly = false;
    updateViewerSettings({shuffleProblems:true, wrongOnlyProblems:false});
    saveChapterLearning();
    syncProbTools();
    renderProblems();
    showPage('problems');
    window.scrollTo(0, 0);
  });
}

document.getElementById('recapList').addEventListener('click', function(e){
  var link = e.target.closest('.recap-link');
  if(link){
    if(link.hasAttribute('data-sec')){
      gotoSection(link.getAttribute('data-sec'));
    } else {
      gotoFormula(link.getAttribute('data-fid'));
    }
    armJumpBack('recap');  // 자가점검에서 점프해 온 동안만 복귀 칩 표시
    return;
  }
  var btn = e.target.closest('.recap-btn');
  if(!btn) return;
  var group = btn.closest('.recap-toggle');
  group.querySelectorAll('.recap-btn').forEach(function(b){ b.classList.remove('picked-yes', 'picked-no'); });
  var isYes = btn.getAttribute('data-val') === 'yes';
  btn.classList.add(isYes ? 'picked-yes' : 'picked-no');
  var linksEl = btn.closest('.recap-item').querySelector('.recap-links');
  if(linksEl) linksEl.hidden = isYes;
  recapPicks[btn.getAttribute('data-lo')] = isYes ? 'yes' : 'no';
  saveChapterLearning();
  updateRecapStatus();
});

function gotoSection(sid){
  showPage('theory');
  var el = document.getElementById('theory-' + sid);
  if(el) el.scrollIntoView({behavior:'auto', block:'start'});
}
function gotoFormula(fid){
  var idx = formulaIndexById[fid];
  if(idx === undefined) return;
  if(!isDerivCard(CH.derivation.formulas[idx])){
    showPage('formula');
    var el = document.getElementById('formula-card-' + fid);
    if(el) el.scrollIntoView({block:'start'});
    return;
  }
  derivIndex = idx;
  renderDerivCard();
  showPage('derivation');
  scrollCardToReadingPosition(document.querySelector('#derivCard .fcard'));
}
function reviewJoinAdjacentMarks(){
  Array.prototype.forEach.call(document.querySelectorAll('.review-mark'), function(el){
    el.removeAttribute('data-review-joined');
    el.removeAttribute('data-review-continues');
  });
  Array.prototype.forEach.call(document.querySelectorAll('.review-mark'), function(el){
    var prev = el.previousElementSibling;
    if(!prev || !prev.classList.contains('review-mark')) return;
    if(el.hasAttribute('data-note-quiet') || prev.hasAttribute('data-note-quiet')) return;
    if(el.classList.contains('rv-minor') || prev.classList.contains('rv-minor')) return;
    el.setAttribute('data-review-joined', '');
    prev.setAttribute('data-review-continues', '');
  });
}
function openFormulaHash(hash){
  var match = /^#formula-(f-[A-Za-z0-9_-]+)$/.exec(hash || '');
  if(!match || formulaIndexById[match[1]] === undefined) return false;
  gotoFormula(match[1]);
  return true;
}
document.addEventListener('click', function(e){
  if(e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
  var link = e.target.closest && e.target.closest('a.xlink');
  if(!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
  var url = new URL(link.href, window.location.href);
  if(url.origin !== window.location.origin || url.pathname !== window.location.pathname) return;
  if(openFormulaHash(url.hash)) e.preventDefault();
});
window.addEventListener('hashchange', function(){ openFormulaHash(window.location.hash); });
function scrollCardToReadingPosition(el, topRatio){
  if(!el) return;
  if(el.classList.contains('fcard') || el.classList.contains('pcard')){
    var sec = el.closest('.page');
    var anchor = (sec && sec.querySelector('.stepper-bar')) || el;
    var tb = document.getElementById('tabbar');
    var foff = (tb ? tb.offsetHeight : 56) + 10;
    var ftop = anchor.getBoundingClientRect().top + window.scrollY - foff;
    window.scrollTo(0, Math.max(0, ftop));
    return;
  }
  var ratio = topRatio === undefined ? 0.23 : topRatio;
  var top = el.getBoundingClientRect().top + window.scrollY - Math.round(window.innerHeight * ratio);
  window.scrollTo(0, Math.max(0, top));
}

var currentPage = null;
var pageScroll = {};
function tabTopScroll(){
  var tb = document.getElementById('tabbar');
  if(!tb) return 0;
  var prev = tb.style.position;
  tb.style.position = 'static';
  var top = tb.getBoundingClientRect().top + window.scrollY;   // 읽는 순간 리플로우가 강제된다
  tb.style.position = prev;
  return Math.max(0, Math.round(top));
}
var readerScale = Number(viewerSettings.readerScale) || 1;
function setReaderScale(scale){
  readerScale = Math.max(.9, Math.min(2, Math.round(scale * 100) / 100));
  document.documentElement.style.setProperty('--reader-scale', String(readerScale));
  updateViewerSettings({readerScale:readerScale});
}
function saveReaderPosition(){
  if(!currentPage) return;
  try { localStorage.setItem(chapterStoragePrefix + ':scroll', JSON.stringify({page:currentPage, y:window.scrollY, prac:pracIndex, deriv:derivIndex, example:exampleIndex})); } catch(ignore) {}
}
try {
  if(!Number(viewerSettings.readerScale)){
    var legacyStoredScale = Number(localStorage.getItem(chapterStoragePrefix + ':zoom'));
    if(legacyStoredScale) readerScale = legacyStoredScale;
  }
} catch(ignore) {}
setReaderScale(readerScale);
document.getElementById('zoomIn').addEventListener('click', function(){ setReaderScale(readerScale + .1); });
document.getElementById('zoomOut').addEventListener('click', function(){ setReaderScale(readerScale - .1); });
window.addEventListener('pagehide', saveReaderPosition);
window.addEventListener('scroll', saveReaderPosition, {passive:true});
var PAGE_ORDER = ['lo', 'theory', 'example', 'derivation', 'formula', 'practice', 'problems', 'textbook', 'summary', 'recap'];
function isDerivCard(f){ return !!f && f.kind !== 'summary'; }
function formulaCards(){ return ((CH.derivation && CH.derivation.formulas) || []).filter(function(f){ return !isDerivCard(f); }); }
var HIDEABLE_PAGES = ['example', 'derivation', 'formula', 'practice', 'problems'];
var PAGE_LABEL = {lo:'학습목표', theory:'이론', example:'예제', derivation:'유도', formula:'공식',
                  practice:'연습', problems:'문제', textbook:'교재 문제', summary:'요약', recap:'자가점검'};

var THEORY_LABEL = (CH.theoryLabel || '이론');
PAGE_LABEL.theory = THEORY_LABEL;
jumpBackLabel.theory = THEORY_LABEL;
(function(){
  var tab = document.querySelector('.tabbtn[data-tab="theory"]');
  if(tab) tab.textContent = THEORY_LABEL;
  var loNext = document.getElementById('loNextBtn');
  if(loNext) loNext.textContent = '다음: ' + THEORY_LABEL + ' →';
  var tocTitle = document.querySelector('.theory-toc-title');
  if(tocTitle) tocTitle.textContent = THEORY_LABEL + ' 소주제';
  var toc = document.getElementById('theoryToc');
  if(toc) toc.setAttribute('aria-label', THEORY_LABEL + ' 소주제');
  var tocList = document.getElementById('theoryTocList');
  if(tocList) tocList.setAttribute('aria-label', THEORY_LABEL + ' 소주제 목록');
})();
var DERIV_LABEL = (function(){
  var cards = ((CH.derivation && CH.derivation.formulas) || []);
  if(!cards.length) return '유도';
  var hasDerivation = cards.some(function(c){
    return (c && c.kind ? c.kind : 'derivation') === 'derivation';   // 미선언은 유도가 기본
  });
  return hasDerivation ? '유도' : '공식 정리';
})();
PAGE_LABEL.derivation = DERIV_LABEL;
jumpBackLabel.derivation = DERIV_LABEL;
(function(){
  var tab = document.querySelector('.tabbtn[data-tab="derivation"]');
  if(tab) tab.textContent = DERIV_LABEL;
  var tocTitle = document.querySelector('.deriv-toc-title');
  if(tocTitle) tocTitle.textContent = DERIV_LABEL + ' 소주제';
  var toc = document.getElementById('derivToc');
  if(toc) toc.setAttribute('aria-label', DERIV_LABEL + ' 소주제');
  var tocList = document.getElementById('derivTocList');
  if(tocList) tocList.setAttribute('aria-label', DERIV_LABEL + ' 소주제 목록');
})();
var hiddenPages = (function(){
  var out = [];
  function push(name){ if(out.indexOf(name) === -1) out.push(name); }
  (CH.hiddenTabs || []).forEach(function(name){
    if(HIDEABLE_PAGES.indexOf(name) !== -1) push(name);
  });
  if(!exampleDeck().length) push('example');
  if(!((CH.derivation && CH.derivation.formulas) || []).some(isDerivCard)) push('derivation');
  if(!((CH.derivation && CH.derivation.formulas) || []).length) push('formula');
  push('practice');   // 문제 탭 머리로 합쳤다(2026-09-19) — 탭 단추는 늘 숨는다
  if(!(CH.problems || []).length) push('problems');
  if(!((CH.textbookProblems || {}).items || []).length) push('textbook');
  if(!summarySections().length) push('summary');
  return out;
})();
hiddenPages.forEach(function(name){
  var btn = document.querySelector('.tabbtn[data-tab="' + name + '"]');
  if(btn) btn.hidden = true;
});
function pageEmptyInRange(name){
  if(name === 'example') return !exampleDeck().length;
  if(name === 'derivation') return !((CH.derivation && CH.derivation.formulas) || []).some(function(f){ return isDerivCard(f) && formulaInRange(f); });
  if(name === 'formula') return !((CH.derivation && CH.derivation.formulas) || []).some(formulaInRange);
  if(name === 'practice') return true;
  if(name === 'problems') return !(CH.problems || []).some(itemInRange) && !pracDeck().length;
  return false;
}
function nextVisiblePage(from){
  for(var i = PAGE_ORDER.indexOf(from) + 1; i < PAGE_ORDER.length; i++){
    var name = PAGE_ORDER[i];
    if(hiddenPages.indexOf(name) >= 0 || pageEmptyInRange(name)) continue;
    return name;
  }
  return 'recap';
}
function previousVisiblePage(from){
  for(var i = PAGE_ORDER.indexOf(from) - 1; i >= 0; i--){
    var name = PAGE_ORDER[i];
    if(hiddenPages.indexOf(name) >= 0 || pageEmptyInRange(name)) continue;
    return name;
  }
  return 'lo';
}
function lastCardLabel(from, normalNext, normalText){
  var to = nextVisiblePage(from);
  return to === normalNext ? normalText : '다음: ' + PAGE_LABEL[to] + ' →';
}

var tabHistoryStarted = false, restoringTab = false;
function syncTabHistory(name){
  if(restoringTab || !name) return;
  try {
    if(!tabHistoryStarted){ history.replaceState({vtab:name}, ''); tabHistoryStarted = true; }
    else if(!(history.state && history.state.vtab === name)){ history.pushState({vtab:name}, ''); }
  } catch(ignore) {}
}
window.addEventListener('popstate', function(e){
  var name = e.state && e.state.vtab;
  if(!name || name === currentPage) return;
  restoringTab = true;
  try { showPage(name); } finally { restoringTab = false; }
});
window.addEventListener('load', function(){
  if(tabHistoryStarted || !currentPage) return;
  try { history.replaceState({vtab:currentPage}, ''); tabHistoryStarted = true; } catch(ignore) {}
});
function showPage(name, practiceEntryRatio){
  if(name === 'recap' && examLocksRecap()){
    var submit = document.querySelector('.exam-submit');
    if(submit) submit.scrollIntoView({block:'center', behavior:'smooth'});
    return;
  }
  if(name === 'practice') name = 'problems';
  if(currentPage) pageScroll[currentPage] = window.scrollY;
  if(name !== 'example') exampleReturnSection = null;
  if(name === 'formula') renderFormulaList();
  var firstPracticeEntry = (name === 'practice' || name === 'example') && !Object.prototype.hasOwnProperty.call(pageScroll, name);
  document.querySelectorAll('.page').forEach(function(el){
    el.classList.toggle('active', el.getAttribute('data-page') === name);
  });
  document.querySelectorAll('.tabbtn').forEach(function(el){
    el.classList.toggle('active', el.getAttribute('data-tab') === name);
  });
  currentPage = name;
  syncTabHistory(name);
  document.getElementById('tabbar').setAttribute('data-theory-active', String(name === 'theory'));
  document.documentElement.classList.toggle('theory-active', name === 'theory');
  document.documentElement.classList.toggle('derivation-active', name === 'derivation');
  document.documentElement.classList.toggle('practice-active', name === 'practice' || name === 'example');
  document.documentElement.classList.toggle('problems-active', name === 'problems');
  if(name !== 'theory') setTheoryTocOpen(false);
  if(name !== 'derivation') setDerivTocOpen(false);
  if(Object.prototype.hasOwnProperty.call(pageScroll, name)) window.scrollTo(0, pageScroll[name]);
  else window.scrollTo(0, tabTopScroll());
  saveReaderPosition();  // 탭 전환도 즉시 저장 — 스크롤 안 해도 마지막 화면이 새로고침 후 유지된다 (2026-07-27)
  if(firstPracticeEntry){
    var entryCardSel = '#' + (name === 'example' ? 'exampleCard' : 'pracCard') + ' .pcard';
    requestAnimationFrame(function(){
      scrollCardToReadingPosition(document.querySelector(entryCardSel), practiceEntryRatio === undefined ? 0.16 : practiceEntryRatio);
    });
  }
  if(name === 'theory') syncTheoryTocFromScroll();
  paintGivenChips(document);
}
document.getElementById('tabbar').addEventListener('click', function(e){
  var btn = e.target.closest('.tabbtn');
  if(!btn) return;
  document.getElementById('jumpBack').hidden = true;  // 직접 탭 이동 = 점프 흐름 종료
  showPage(btn.getAttribute('data-tab'));
});
function startFromTop(name){
  delete pageScroll[name];        // 스크롤형·카드형 공통 — 저장 위치를 버려야 탭 맨 위로 착지한다
  if(name === 'example'){ exampleIndex = 0; renderExampleCard(); }
  if(name === 'derivation'){
    var fsAll = (CH.derivation && CH.derivation.formulas) || [];
    var firstIn = fsAll.findIndex(function(f){ return isDerivCard(f) && formulaInRange(f); });
    derivIndex = firstIn >= 0 ? firstIn : Math.max(0, fsAll.findIndex(isDerivCard));
    renderDerivCard();
  }
  if(name === 'practice' || name === 'problems'){ pracIndex = 0; renderPracCard(); }
}
document.getElementById('loNextBtn').addEventListener('click', function(){
  startFromTop('theory'); showPage('theory');
});
document.getElementById('theoryNextBtn').addEventListener('click', function(){
  var target = theoryNextTarget();
  startFromTop(target);
  showPage(target);
});
function lastTheorySection(){
  var inRange = (typeof sectionInRange === 'function') ? sectionInRange : function(){ return true; };
  return passSections().filter(function(s){ return !isChapterSummary(s) && inRange(s.id); }).slice(-1)[0] || null;
}
function theoryNextTarget(){
  var last = lastTheorySection();
  if(last && passSectionDeckIndex(last.id) < 0) return nextVisiblePage('example');
  return nextVisiblePage('theory');
}
function syncTheoryNext(){
  var btn = document.getElementById('theoryNextBtn');
  var last = lastTheorySection();
  btn.hidden = !!last && passSectionDeckIndex(last.id) >= 0;
  var to = theoryNextTarget();
  btn.textContent = to === nextVisiblePage('theory')
    ? lastCardLabel('theory', 'example', '다음: 예제 →') : '다음: ' + PAGE_LABEL[to] + ' →';
}
document.getElementById('probNextBtn').addEventListener('click', function(){
  var target = nextVisiblePage('problems');
  startFromTop(target); showPage(target);     // 요약·자가점검 둘 다 스크롤형이라 같은 부류다
});
document.getElementById('probNextBtn').textContent =
  lastCardLabel('problems', 'summary', '다음: 요약 →');
document.getElementById('summaryNextBtn').addEventListener('click', function(){
  startFromTop('recap'); showPage('recap');
});
var SUBQ_KEY = /^\*{0,2}\(([a-e]|iv|i{1,3}|v|종합|공통|정리)\)\*{0,2}\s*/;
var SUBQ_SPLIT = /\s*(?=\((?:[a-e]|iv|i{1,3}|v|종합|공통|정리)\))/;
document.getElementById('textbookNextBtn').addEventListener('click', function(){
  var target = nextVisiblePage('textbook');
  startFromTop(target); showPage(target);
});
document.getElementById('textbookNextBtn').textContent =
  lastCardLabel('textbook', 'summary', '다음: 요약 →');
function textbookInRange(it){
  if(!it) return true;
  if(it.section) return sectionInRange(it.section);
  var objs = it.objectives || [];
  if(!objs.length) return progressIsFull();
  var los = {};
  (CH.learningObjectives || []).forEach(function(lo){ if(lo && lo.id) los[lo.id] = lo; });
  return objs.some(function(o){
    var secs = (los[o] && los[o].relatedSections) || [];
    return secs.some(function(sid){ return sectionInRange(sid); });
  });
}
function renderTextbook(){
  var tb = CH.textbookProblems || {};
  var items = (tb.items || []).filter(textbookInRange);
  var host = document.getElementById('textbookList');
  if(!items.length){ host.innerHTML = ''; return; }
  var head = '<div class="tb-head">' + fmtText(tb.source || '') +
    (tb.note ? '<div class="tb-note">' + fmtText(tb.note) + '</div>' : '') + '</div>';
  host.innerHTML = head + items.map(function(it, i){
    var outline = (it.outline && it.outline.length)
      ? '<ol class="q-outline">' + it.outline.map(function(st){
          return '<li>' + renderStep(st) + '</li>'; }).join('') + '</ol>'
      : '';
    return '<article class="qcard tb-card' + reviewClass(it, 'answer') + '" id="tb-' + esc(it.id) + '">' +
      '<div class="tb-ref">' + (function(r){
        var s = String(r || ''), k = s.indexOf(' — ');
        return k < 0 ? fmtText(s) : fmtText(s.slice(0, k)) + ' <span class="tb-ref-note">— ' + fmtText(s.slice(k + 3)) + '</span>';
      })(it.ref) + (it.topic ? ' <span class="tb-topic">· ' + fmtText(it.topic) + '</span>' : '') + '</div>' +
      '<details class="q-answer"><summary>정답 · 풀이 뼈대 펼치기 (먼저 스스로 푼 다음에)</summary>' +
        (it.why ? '<div class="tb-why' + reviewClass(it, 'why') + '">' + fmtText(it.why) + '</div>' : '') +
        '<div class="q-ans-val' + reviewClass(it, 'answer') + '">' + renderAnswer(it.answer || '') + '</div>' +
        (outline ? '<div class="q-outline-wrap' + reviewClass(it, 'outline') + '">' + outline + '</div>' : '') +
      '</details></article>';
  }).join('');
}
renderTextbook();

var stageMeta = {
  single_blank: {cls:'stage1', label:'1단계 · 빈칸 채우기'},
  multi_blank: {cls:'stage1', label:'1단계 · 빈칸 여러 개'},
  process_fill: {cls:'stage2', label:'2단계 · 풀이 통째로 쓰기'},
  assembly: {cls:'stage3', label:'3단계 · 구조 조립'}
};
var diffLabel = {basic:'기초', intermediate:'중급', advanced:'변별'};
function diffBadge(d){
  var known = Object.prototype.hasOwnProperty.call(diffLabel, d);
  return '<span class="badge diff diff-' + esc(known ? d : 'unknown') + '">' +
         esc(known ? diffLabel[d] : '난이도 미표기') + '</span>';
}

function splitRelation(src){
  if (typeof src !== 'string') return null;
  var depth = 0;
  for (var i = 0; i < src.length; i++) {
    var c = src.charAt(i);
    if (c === '\\') { i++; continue; }          // 제어열 다음 글자는 구조가 아니다
    if (c === '{') depth++;
    else if (c === '}') depth--;
    else if (c === '=' && depth === 0) {
      var lhs = src.slice(0, i).trim(), rhs = src.slice(i + 1).trim();
      return (lhs && rhs) ? {lhs: lhs, rhs: rhs} : null;
    }
  }
  return null;
}
function renderMathLines(latex){
  var lines = Array.isArray(latex) ? latex : [latex];
  var parts = lines.map(function(l){ return Array.isArray(l) ? null : splitRelation(l); });
  if (lines.length > 1 && parts.every(function(p){ return p; })) {
    return '<div class="fmath-lines aligned">' + parts.map(function(p){
      return '<div class="fmath-line">'
        + '<span class="eq-lhs">' + renderMath(p.lhs) + '</span>'
        + '<span class="eq-rel">=</span>'
        + '<span class="eq-rhs">' + renderMath(p.rhs) + '</span></div>';
    }).join('') + '</div>';
  }
  return lines.map(function(l){
    if(Array.isArray(l)){
      return '<div class="fmath-line fmath-cols">' + l.map(function(c){
        return '<div class="fmath-col">' + renderMath(c) + '</div>';
      }).join('') + '</div>';
    }
    return '<div class="fmath-line">' + renderMath(l) + '</div>';
  }).join('');
}


var ANS_NUM_KEY = /^#(\d+)\s*[:：]\s*/;
var ANS_NUM_SPLIT = /\s*(?=#\d+\s*[:：])/;
function splitAnswerItems(s){
  var out = [], buf = '', depth = 0, math = false;
  for(var i = 0; i < s.length; i++){
    var c = s[i];
    if(c === '\\' && (s[i+1] === '(' || s[i+1] === ')')){ math = s[i+1] === '('; buf += c + s[i+1]; i++; continue; }
    if(!math){
      if('(〈⟨[{'.indexOf(c) >= 0) depth++;
      else if(')〉⟩]}'.indexOf(c) >= 0) depth = Math.max(0, depth - 1);
      else if(depth === 0 && (s.substr(i, 2) === ', ' || s.substr(i, 3) === ' · ')){
        if(buf.trim()) out.push(buf.trim());
        buf = ''; i += (s[i] === ',' ? 1 : 2); continue;
      }
    }
    buf += c;
  }
  if(buf.trim()) out.push(buf.trim());
  return out;
}
function renderAnswerNumbered(parts){
  return parts.map(function(p){
    var m = p.match(ANS_NUM_KEY);
    var body = m ? p.slice(m[0].length) : p;
    var items = splitAnswerItems(body);
    return '<div class="ans-part ans-num"><span class="ans-key">' + (m ? '#' + esc(m[1]) : '') + '</span>'
      + '<span class="ans-items">' + items.map(function(x){ return '<span class="ans-item">' + fmtText(x) + '</span>'; }).join('')
      + '</span></div>';
  }).join('');
}
function renderAnswer(text){
  var s = String(text == null ? '' : text);
  var numbered = s.split(ANS_NUM_SPLIT).filter(function(p){ return p.trim(); });
  if(numbered.length >= 2 && ANS_NUM_KEY.test(numbered[0])) return renderAnswerNumbered(numbered);
  var parts = s.split(SUBQ_SPLIT).filter(function(p){ return p.trim(); });
  if(parts.length < 2) return fmtText(s);
  return parts.map(function(p){
    var m = p.match(SUBQ_KEY);
    if(!m) return '<div class="ans-part">' + fmtText(p) + '</div>';
    return '<div class="ans-part"><span class="ans-key">(' + esc(m[1]) + ')</span>' +
           fmtText(p.slice(m[0].length)) + '</div>';
  }).join('');
}

function renderOutline(steps){
  var groups = [], cur = null;
  (steps || []).forEach(function(st){
    var body = st, key = null;
    var isObj = st && typeof st === 'object' && !Array.isArray(st);
    var head = typeof st === 'string' ? st : (isObj ? String(st.text || '') : '');
    var m = head.match(SUBQ_KEY);
    if(m){
      key = m[1];
      if(isObj){
        var cp = {};
        for(var k in st){ if(Object.prototype.hasOwnProperty.call(st, k)) cp[k] = st[k]; }
        cp.text = head.slice(m[0].length);
        body = cp;
      } else {
        body = st.slice(m[0].length);
      }
    }
    if(key !== null || !cur){ cur = { key: key, items: [] }; groups.push(cur); }
    cur.items.push(body);
  });
  var lis = function(items){
    return items.length
      ? '<ol class="q-outline">' + items.map(function(st){ return '<li>' + renderStep(st) + '</li>'; }).join('') + '</ol>'
      : '';
  };
  if(groups.length === 1 && groups[0].key === null) return lis(groups[0].items);
  return groups.map(function(g){
    return (g.key === null ? '' : '<div class="sub-head">(' + esc(g.key) + ')</div>') + lis(g.items);
  }).join('');
}

function splitChainEq(raw){
  var s = String(raw == null ? '' : raw);
  var idx = s.indexOf('=');
  if(idx < 0) return null;
  return {lhs: s.slice(0, idx).trim(), rhs: s.slice(idx).trim()};
}
function renderEqGroup(list){
  var eqs = list || [];
  if(eqs.length < 2){
    return eqs.map(function(e){ return '<div class="steq mono">' + renderMath(e) + '</div>'; }).join('');
  }
  var cells = eqs.map(function(e){
    var sp = splitChainEq(e);
    if(!sp) return '<div class="steq steq-full mono">' + renderMath(e) + '</div>';
    return '<div class="steq steq-lhs mono">' + renderMath(sp.lhs) + '</div>' +
           '<div class="steq steq-rhs mono">' + renderMath(sp.rhs) + '</div>';
  }).join('');
  return '<div class="steq-chain">' + cells + '</div>';
}
function renderStep(st){
  if(st && typeof st === 'object' && !Array.isArray(st)){
    var eqs = st.equations || [];
    var paras = st.text != null ? String(st.text).split(/\n{2,}/) : [];
    if(paras.length > 1 && paras.length === eqs.length){
      return paras.map(function(p, i){
        return '<div class="sttext">' + fmtText(p) + '</div>' + renderEqGroup([eqs[i]]);
      }).join('');
    }
    var eqsHtml = renderEqGroup(eqs);
    return (st.text ? '<div class="sttext">' + fmtText(st.text) + '</div>' : '') + eqsHtml;
  }
  return fmtText(st);
}

var derivIndex = 0;

var derivSlideStep = 0;
var derivSlideCur = null;
function derivSlideSpec(f){
  var fig = f && f.figure;
  var steps = (f && f.derivationSteps) || [];
  if(!fig || !fig.svg || !steps.some(function(st){ return st && typeof st === 'object' && st.show; })) return null;
  var ids = [];
  steps.forEach(function(st){
    ((st && st.show) || []).forEach(function(gid){ if(ids.indexOf(gid) === -1) ids.push(gid); });
  });
  var groups = [];
  steps.forEach(function(st, i){
    var show = (st && st.show) || ids;
    var key = show.slice().sort().join('');
    var last = groups[groups.length - 1];
    if(last && last.key === key) last.indices.push(i); else groups.push({key: key, show: show, indices: [i]});
  });
  return { fig: fig, steps: steps, ids: ids, groups: groups };
}
function applyDerivSlide(slide){
  derivSlideCur = slide || null;
  if(!slide) return;
  var card = document.getElementById('derivCard');
  var on = !!viewerSettings.derivSlideMode;
  var groups = slide.groups;
  if(derivSlideStep >= groups.length) derivSlideStep = groups.length - 1;
  if(derivSlideStep < 0) derivSlideStep = 0;
  function setHidden(el, want){
    if(want) el.setAttribute('hidden', ''); else el.removeAttribute('hidden');
  }
  var lis = card.querySelectorAll('.fsteps > li');
  var curGroup = groups[derivSlideStep] || { indices: [] };
  for(var i = 0; i < lis.length; i++) setHidden(lis[i], on && curGroup.indices.indexOf(i) === -1);
  var cur = { show: curGroup.show };
  var last = slide.steps[slide.steps.length - 1] || {};
  var showing = on ? (cur.show || slide.ids) : (last.show || slide.ids);
  var fig = card.querySelector('.fslide-fig');
  var prevShow = derivSlideStep > 0 ? groups[derivSlideStep - 1].show : null;
  var entering = (on && prevShow)
    ? showing.filter(function(gid){ return prevShow.indexOf(gid) === -1; }) : [];
  var carried = on && !!prevShow;               // 첫 단계에는 «앞 단계» 가 없다 — 아무것도 안 연하게 한다
  slide.ids.forEach(function(gid){
    var el = fig && fig.querySelector('[id="' + String(gid).replace(/"/g, '\\"') + '"]');
    if(!el){ console.warn('[슬라이드] 삽화에서 그룹을 못 찾았다 — ' + gid); return; }
    setHidden(el, showing.indexOf(gid) === -1);
    el.classList.toggle('fslide-old', !!carried && showing.indexOf(gid) !== -1
                                      && entering.indexOf(gid) === -1);
  });
  (slide.fig._reviewChangedGroups || []).forEach(function(gid){
    var el = fig && fig.querySelector('[id="' + String(gid).replace(/"/g, '\\"') + '"]');
    if(!el) return;
    el.classList.add('fslide-changed');
    if(!el.querySelector(':scope > rect.fslide-changed-bg')){
      try{
        var bb = el.getBBox();
        if(bb.width > 0 && bb.height > 0){
          var pad = 4;
          var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
          rect.setAttribute('class', 'fslide-changed-bg');
          rect.setAttribute('fill', 'none');
          rect.setAttribute('pointer-events', 'none');
          rect.setAttribute('x', bb.x - pad);
          rect.setAttribute('y', bb.y - pad);
          rect.setAttribute('width', bb.width + pad * 2);
          rect.setAttribute('height', bb.height + pad * 2);
          rect.setAttribute('rx', 4);
          el.insertBefore(rect, el.firstChild);
        }
      }catch(e){}
    }
  });
  var toggle = card.querySelector('[data-slide-toggle]');
  var count = card.querySelector('.fslide-count');
  var nav = card.querySelector('.fslide-nav');
  if(toggle){
    toggle.textContent = '슬라이드: ' + (on ? '켜짐' : '꺼짐');
    toggle.classList.toggle('on', on);
  }
  if(count){
    setHidden(count, !on);          // HTML 이라 프로퍼티도 되지만 한 자리에서 한 방식만 쓴다
    count.textContent = '단계 ' + (derivSlideStep + 1) + ' / ' + groups.length;
  }
  if(nav){
    setHidden(nav, !on);
    var prev = nav.querySelector('[data-slide-prev]'), next = nav.querySelector('[data-slide-next]');
    if(prev) prev.disabled = derivSlideStep === 0;
    if(next) next.disabled = derivSlideStep >= groups.length - 1;
  }
}
function renderDerivCard(){
  if(!CH.derivation.formulas.length){
    document.getElementById('derivCard').innerHTML =
      '<div class="fcard"><div class="fcard-name serif">유도 카드 준비 중</div>' +
      '<div class="fnote">이 챕터의 유도 카드는 아직 만들어지지 않았습니다. 먼저 이론 탭을 보세요.</div></div>';
    document.getElementById('derivCounter').textContent = '준비 중';
    document.getElementById('derivDots').innerHTML = '';
    document.getElementById('derivNextBtn').textContent =
      lastCardLabel('derivation', 'practice', '연습으로 →');
    return;
  }
  if(derivIndex < 0 || derivIndex >= CH.derivation.formulas.length) derivIndex = 0;
  var f = CH.derivation.formulas[derivIndex];
  setDerivTocActive(f.topic);
  var varsHtml = Object.keys(f.variables).map(function(k){
    return '<div><b class="imath">' + renderMath(k) + '</b> – ' + fmtText(f.variables[k]) + '</div>';
  }).join('');
  var slide = derivSlideSpec(f);
  derivSlideStep = 0;                     // 카드가 바뀌면 첫 단계부터 — 남의 단계 번호를 물려받지 않는다
  var stepsHtml = f.derivationSteps.map(function(st){
    return '<li>' + renderStep(st) + '</li>';
  }).join('');
  var slideFigHtml = !slide ? '' :
    '<div class="fslide-fig">' + slide.fig.svg + '</div>';
  var slideBarHtml = !slide ? '' :
    '<div class="fslide-bar">' +
      '<button class="tool-toggle" type="button" id="derivSlideToggle" data-setting-keys="derivSlideMode" data-slide-toggle>슬라이드: 꺼짐</button>' +
      '<span class="fslide-count" hidden></span>' +
      '<span class="fslide-nav" hidden>' +
        '<button class="fslide-btn" type="button" data-slide-prev>← 이전 단계</button>' +
        '<button class="fslide-btn" type="button" data-slide-next>다음 단계 →</button>' +
      '</span>' +
    '</div>';
  var appliesHtml = f.appliesTo
    ? '<div class="fapplies"><span class="fapplies-k">이런 형태일 때</span>'
      + '<span>' + fmtText(f.appliesTo) + '</span></div>'
    : '';
  var tagsHtml = f.assumptions.map(function(a){ return '<span class="ftag">' + fmtText(a) + '</span>'; }).join('');
  var srcHtml = '';
  document.getElementById('derivCard').innerHTML =
    '<div class="fcard' + (formulaInRange(f) ? '' : ' out-of-range') + '">' +
      '<div class="ftopic">' + esc(f.topic) + '</div>' +
      '<div class="fcard-name serif">' + fmtText(f.name) + '</div>' +
      appliesHtml +
      '<div class="fmath mono' + reviewClass(f, 'latex') + '">' + renderMathLines(f.latex) + '</div>' +
      renderDiagrams(f.diagrams, f) +
      '<div class="fvars' + reviewClass(f, 'variables') + '">' + varsHtml + '</div>' +
      slideFigHtml +
      '<ol class="fsteps' + reviewClass(f, 'derivationSteps') + '">' + stepsHtml + '</ol>' +
      slideBarHtml +
      '<div class="ftag-row">' + tagsHtml + '</div>' +
      '<div class="fnote' + reviewClass(f, 'notes') + '">' + fmtText(f.notes) + srcHtml + '</div>' +
      renderPitfalls(f.pitfalls, f) +
      renderComprehensionChecks(f.comprehensionChecks || [], f) +
    '</div>';
  applyDerivSlide(slide);                 // 선언이 없으면(slide === null) 아무것도 안 한다
  var derivOnly = CH.derivation.formulas.filter(isDerivCard);
  document.getElementById('derivCounter').textContent = (derivOnly.indexOf(f) + 1) + ' / ' + derivOnly.length;
  document.getElementById('derivDots').innerHTML = CH.derivation.formulas.map(function(formula, i){
    if(!isDerivCard(formula)) return '';
    var topicStart = i > 0 && formula.topic !== CH.derivation.formulas[i - 1].topic;
    return '<button class="stepper-dot' + (topicStart ? ' topic-start' : '') + (i === derivIndex ? ' current' : '')
      + (formulaInRange(formula) ? '' : ' out-of-range') + '" data-i="' + i + '" title="공식 ' + (i+1) + ' · ' + esc(formula.topic)
      + (formulaInRange(formula) ? '' : ' (진도 밖)') + '"></button>';
  }).join('');
  var nextBtn = document.getElementById('derivNextBtn');
  nextBtn.textContent = (derivStep(derivIndex, 1) < 0)
    ? lastCardLabel('derivation', 'practice', '연습으로 →') : '다음 →';
}
document.getElementById('derivDots').addEventListener('click', function(e){
  var dot = e.target.closest('.stepper-dot');
  if(!dot) return;
  derivIndex = Number(dot.getAttribute('data-i'));
  renderDerivCard();
  scrollCardToReadingPosition(document.querySelector('#derivCard .fcard'));
});
document.getElementById('derivCard').addEventListener('click', function(e){
  if(!derivSlideCur) return;
  var t = e.target.closest ? e.target.closest('button') : null;
  if(!t) return;
  if(t.hasAttribute('data-slide-toggle')){
    updateViewerSettings({derivSlideMode: !viewerSettings.derivSlideMode});
    derivSlideStep = 0;                   // 켤 때는 첫 단계부터 — 꺼져 있던 동안의 번호는 뜻이 없다
    applyDerivSlide(derivSlideCur);
    return;
  }
  var n = derivSlideCur.groups.length;
  if(t.hasAttribute('data-slide-prev')){ derivSlideStep = Math.max(0, derivSlideStep - 1); applyDerivSlide(derivSlideCur); return; }
  if(t.hasAttribute('data-slide-next')){ derivSlideStep = Math.min(n - 1, derivSlideStep + 1); applyDerivSlide(derivSlideCur); }
});
function derivStep(from, dir){
  var fs = (CH.derivation && CH.derivation.formulas) || [];
  for(var i = from + dir; i >= 0 && i < fs.length; i += dir){
    if(isDerivCard(fs[i]) && formulaInRange(fs[i])) return i;
  }
  return -1;
}
function renderFormulaList(){
  var box = document.getElementById('formulaList');
  if(!box) return;
  var fs = (CH.derivation && CH.derivation.formulas) || [];
  var normTex = function(s){ return String(s || '').replace(/\\[,;!:]|\s+/g, '').replace(/,$/, ''); };
  var byTex = {};
  fs.forEach(function(f){ if(isDerivCard(f) && typeof f.latex === 'string') byTex[normTex(f.latex)] = f.id; });
  var pieces = function(l){ return String(l).split(/,?\s*\\qquad|,?\s*\\quad/).filter(function(x){ return x.trim(); }); };
  var refsOf = function(f){
    return [].concat(f.latex || []).map(function(l, i){
      var r = Array.isArray(f.latexRefs) ? f.latexRefs[i] : undefined;
      if(r !== undefined) return r;
      var hit = pieces(l).map(function(p){ return byTex[normTex(p)]; }).filter(Boolean);
      return hit.length ? hit[0] : null;
    });
  };
  var covered = {};
  fs.forEach(function(f){ if(!isDerivCard(f)) refsOf(f).forEach(function(r){ if(r) covered[r] = true; }); });
  var goBtn = function(fid){ return ' <button class="formula-row-go" type="button" data-fid="' + esc(fid) + '">유도 보기</button>'; };
  box.innerHTML = fs.filter(function(f){ return !(isDerivCard(f) && covered[f.id]); }).map(function(f){
    var refs = isDerivCard(f) ? [] : refsOf(f);
    var entries = [].concat(f.latex || []);
    var body = entries.map(function(l, i){
      var ps = pieces(l).map(function(p){ return p.trim(); });
      var mono = function(p){ return '<span class="formula-piece mono">' + renderMath(p) + '</span>'; };
      var go = refs[i] ? goBtn(refs[i]) : '';
      if(ps.length < 3) return '<div class="fmath-line formula-line">' + ps.map(mono).join('') + go + '</div>';
      return '<div class="fmath-line formula-line">' + mono(ps[0]) + go + '</div>' +
        '<div class="formula-where"><span class="formula-where-tag">여기서</span><span class="formula-where-list">' +
          ps.slice(1).map(function(p){ return '<span class="formula-where-item">' + mono(p) + '</span>'; }).join('') +
        '</span></div>';
    }).join('');
    return '<div class="formula-row' + (formulaInRange(f) ? '' : ' out-of-range') + '" id="formula-card-' + esc(f.id) + '">' +
      '<div class="formula-row-name">' + fmtText(f.name) + (isDerivCard(f) ? goBtn(f.id) : '') + '</div>' +
      '<div class="fmath mono formula-row-math' + reviewClass(f, 'latex') + '">' + body + '</div>' +
    '</div>';
  }).join('');
  document.getElementById('formulaNextBtn').textContent = '다음: ' + PAGE_LABEL[nextVisiblePage('formula')] + ' →';
}
document.getElementById('formulaList').addEventListener('click', function(e){
  var b = e.target.closest ? e.target.closest('.formula-row-go') : null;
  if(b) gotoFormula(b.getAttribute('data-fid'));
});
document.getElementById('formulaNextBtn').addEventListener('click', function(){
  var after = nextVisiblePage('formula');
  startFromTop(after); showPage(after);
});
document.getElementById('derivPrevBtn').addEventListener('click', function(){
  var prevIdx = derivStep(derivIndex, -1);
  if(prevIdx >= 0){ derivIndex = prevIdx; renderDerivCard(); scrollCardToReadingPosition(document.querySelector('#derivCard .fcard')); return; }
  if(true){
    var beforeDeriv = previousVisiblePage('derivation');
    if(beforeDeriv === 'example'){ exampleIndex = Math.max(0, exampleDeck().length - 1); renderExampleCard(); }
    showPage(beforeDeriv);
    return;
  }
  derivIndex -= 1;
  renderDerivCard();
  scrollCardToReadingPosition(document.querySelector('#derivCard .fcard'));
});
document.getElementById('derivNextBtn').addEventListener('click', function(){
  var nextIdx = derivStep(derivIndex, 1);
  if(nextIdx < 0){
    var after = nextVisiblePage('derivation');
    startFromTop(after);
    showPage(after, after === 'practice' ? 0.23 : undefined); return;   // 저장 스크롤도 함께 버린다
  }
  derivIndex = nextIdx;
  renderDerivCard();
  scrollCardToReadingPosition(document.querySelector('#derivCard .fcard'));
});

function pracDeck(){
  return (CH.practice || []).filter(function(p){ return p.difficulty !== 'basic' && itemInRange(p); });
}
var pracIndex = 0;
function renderPracCard(){
  var deck = pracDeck();
  var pracBlock = document.getElementById('pracBlock');
  if(pracBlock) pracBlock.hidden = !deck.length;
  if(!deck.length){
    document.getElementById('pracCard').innerHTML =
      '<article class="pcard"><div class="prompt">연습 카드 준비 중</div>' +
      '<div class="expected-lock">이 챕터의 연습은 아직 만들어지지 않았습니다. 먼저 이론 탭을 보세요.</div></article>';
    document.getElementById('pracCounter').textContent = '준비 중';
    document.getElementById('pracDots').innerHTML = '';
    document.getElementById('pracNextBtn').textContent =
      lastCardLabel('practice', 'problems', '문제로 →');
    return;
  }
  if(pracIndex < 0 || pracIndex >= deck.length) pracIndex = 0;
  var p = deck[pracIndex];
  var sm = stageMeta[p.stage] || {cls:'stage1', label:'연습'};
  var blankById = {};
  p.blanks.forEach(function(b){ blankById[b.id] = b; });
  var sub = '';
  if(p.givenSubResults && p.givenSubResults.length){
    var rows = p.givenSubResults.map(function(sr){
      return '<div class="sr-row"><span class="sr-label">' + fmtText(sr.label) + '</span>'
        + (sr.symbol ? '<span class="sr-sym">' + fmtText(sr.symbol) + '</span>' : '')
        + '<span class="sr-val mono">' + fmtText(sr.value) + '</span></div>';
    }).join('');
    sub = '<div class="subresults"><div class="sr-h">이미 계산된 값 – 조합 구조만 완성하면 됩니다</div>' + rows + '</div>';
  }
  var singleBlank = p.blanks.length === 1;
  var answers = p.blanks.map(function(b){
    var head = singleBlank ? '정답' : '빈칸 ' + esc(b.id.replace('BLANK_',''));
    return '<details id="ans-' + esc(b.id) + '">' +
        '<summary><span class="tick">●</span> ' + head + '</summary>' +
        '<div class="ans-body">' +
          '<div class="ans-answer mono">' + renderMath(b.answer) + '</div>' +
          '<div class="ans-expl">' + fmtText(b.explanation) + '</div>' +
        '</div>' +
      '</details>';
  }).join('');
  document.getElementById('pracCard').innerHTML =
    '<article class="pcard">' +
      '<div class="pcard-read">' +
        '<div class="pcard-top">' +
          '<span class="badge ' + sm.cls + '">' + sm.label + '</span>' +
          diffBadge(p.difficulty) +
        '</div>' +
        '<div class="prompt' + reviewClass(p, 'prompt') + '">' + fmtText(glossedPrompt(p)) + '</div>' +
        renderDiagrams(p.diagrams, p) +
      '</div>' +
      '<div class="pcard-work">' +
        sub +
        '<div class="soltpl mono' + reviewClass(p, 'solutionTemplate') + '">' + renderMath(p.solutionTemplate) + '</div>' +
        '<div class="answers' + reviewClass(p, 'blanks') + '">' + answers + '</div>' +
        (p.expectedOutput ?
          '<div class="expected-lock">' + (singleBlank ? '빈칸 답을 펼치면' : '빈칸 답을 모두 펼치면') + ' 최종 답이 표시됩니다.</div>' +
          '<div class="expected' + reviewClass(p, 'expectedOutput') + '" hidden><span>최종 답</span><b class="mono">' + fmtText(p.expectedOutput) + '</b></div>' : '') +
      '</div>' +
    '</article>';
  var answerDetails = document.querySelectorAll('#pracCard .answers details');
  var expected = document.querySelector('#pracCard .expected');
  var lock = document.querySelector('#pracCard .expected-lock');
  function syncExpected(){
    if(!expected || !lock) return;
    var done = Array.prototype.every.call(answerDetails, function(d){ return d.open; });
    expected.hidden = !done;
    lock.hidden = done;
  }
  function syncInlineBlank(detail){
    var id = detail.id.replace('ans-', '');
    var blank = blankById[id];
    if(!blank) return;
    document.querySelectorAll('#pracCard .blankbtn[data-blank-id="' + id + '"]').forEach(function(btn){
      btn.classList.toggle('filled', detail.open);
      btn.title = detail.open ? '정답 숨기기' : '정답 보기';
      btn.innerHTML = detail.open ? renderMath(blank.answer) : '___';
    });
    if(blank.figureSlot){
      var slot = document.getElementById(blank.figureSlot);
      if(slot){
        var tmp = document.createElement('div');
        tmp.innerHTML = renderMath(blank.figureAnswer || blank.answer);
        slot.textContent = detail.open ? tmp.textContent : '?';
        slot.classList.toggle('filled-answer-slot', detail.open);
      }
    }
    if(detail.open) revealConditionsIn(document.getElementById('pracCard'));   // W-36
  }
  answerDetails.forEach(function(d){
    d.addEventListener('toggle', function(){
      syncInlineBlank(d);
      syncExpected();
    });
  });
  syncExpected();
  document.getElementById('pracCounter').textContent = (pracIndex + 1) + ' / ' + deck.length;
  document.getElementById('pracDots').innerHTML = deck.map(function(_, i){
    return '<button class="stepper-dot' + (i === pracIndex ? ' current' : '') + '" data-i="' + i + '" title="문제 ' + (i+1) + '"></button>';
  }).join('');
  var nextBtn = document.getElementById('pracNextBtn');
  var problemsBelow = pracIndex === deck.length - 1 && (CH.problems || []).some(itemInRange);
  nextBtn.hidden = problemsBelow;
  nextBtn.textContent = (pracIndex === deck.length - 1)
    ? (problemsBelow ? '' : lastCardLabel('problems', 'textbook', '교재 문제로 →')) : '다음 →';
}
document.getElementById('pracDots').addEventListener('click', function(e){
  var dot = e.target.closest('.stepper-dot');
  if(!dot) return;
  pracIndex = Number(dot.getAttribute('data-i'));
  renderPracCard();
  scrollCardToReadingPosition(document.querySelector('#pracCard .pcard'));
});
document.getElementById('pracPrevBtn').addEventListener('click', function(){
  if(pracIndex === 0){
    var beforePrac = previousVisiblePage('practice');
    if(beforePrac === 'derivation'){
      var lastDeriv = -1;
      CH.derivation.formulas.forEach(function(ff, ii){ if(isDerivCard(ff)) lastDeriv = ii; });
      derivIndex = Math.max(0, lastDeriv);
      renderDerivCard();
    } else if(beforePrac === 'example'){
      exampleIndex = Math.max(0, exampleDeck().length - 1);
      renderExampleCard();
    }
    showPage(beforePrac);
    return;
  }
  pracIndex -= 1;
  renderPracCard();
  scrollCardToReadingPosition(document.querySelector('#pracCard .pcard'));
});
document.getElementById('pracNextBtn').addEventListener('click', function(){
  if(pracIndex >= pracDeck().length - 1){
    var probList = document.getElementById('probList');
    if((CH.problems || []).some(itemInRange) && probList){ probList.scrollIntoView({block:'start', behavior:'smooth'}); return; }
    var afterPrac = nextVisiblePage('problems');
    startFromTop(afterPrac); showPage(afterPrac); return;
  }
  pracIndex += 1;
  renderPracCard();
  scrollCardToReadingPosition(document.querySelector('#pracCard .pcard'));
});

function exampleDeck(){
  var sectionOrder = {};
  passSections().forEach(function(sec, index){ sectionOrder[sec.id] = index; });
  return (CH.practice || []).map(function(p, index){ return {item:p, index:index}; })
    .filter(function(entry){ return entry.item.difficulty === 'basic' && itemInRange(entry.item); })
    .sort(function(a, b){
      var ai = Object.prototype.hasOwnProperty.call(sectionOrder, a.item.section) ? sectionOrder[a.item.section] : Infinity;
      var bi = Object.prototype.hasOwnProperty.call(sectionOrder, b.item.section) ? sectionOrder[b.item.section] : Infinity;
      return ai - bi || a.index - b.index;
    })
    .map(function(entry){ return entry.item; });
}
var exampleIndex = 0;
function renderExampleCard(){
  var deck = exampleDeck();
  if(!deck.length){
    document.getElementById('exampleCard').innerHTML =
      '<article class="pcard"><div class="prompt">예제 카드 준비 중</div>' +
      '<div class="expected-lock">이 챕터의 예제는 아직 만들어지지 않았습니다.</div></article>';
    document.getElementById('exampleCounter').textContent = '준비 중';
    document.getElementById('exampleDots').innerHTML = '';
    return;
  }
  if(exampleIndex < 0 || exampleIndex >= deck.length) exampleIndex = 0;
  var p = deck[exampleIndex];
  var sm = stageMeta[p.stage] || {cls:'stage1', label:'연습'};
  var blankById = {};
  p.blanks.forEach(function(b){ blankById[b.id] = b; });
  var sub = '';
  if(p.givenSubResults && p.givenSubResults.length){
    var rows = p.givenSubResults.map(function(sr){
      return '<div class="sr-row"><span class="sr-label">' + fmtText(sr.label) + '</span>'
        + (sr.symbol ? '<span class="sr-sym">' + fmtText(sr.symbol) + '</span>' : '')
        + '<span class="sr-val mono">' + fmtText(sr.value) + '</span></div>';
    }).join('');
    sub = '<div class="subresults"><div class="sr-h">이미 계산된 값 – 조합 구조만 완성하면 됩니다</div>' + rows + '</div>';
  }
  var singleBlank = p.blanks.length === 1;
  var answers = p.blanks.map(function(b){
    var head = singleBlank ? '정답' : '빈칸 ' + esc(b.id.replace('BLANK_',''));
    return '<details id="ex-ans-' + esc(b.id) + '">' +
        '<summary><span class="tick">●</span> ' + head + '</summary>' +
        '<div class="ans-body">' +
          '<div class="ans-answer mono">' + renderMath(b.answer) + '</div>' +
          '<div class="ans-expl">' + fmtText(b.explanation) + '</div>' +
        '</div>' +
      '</details>';
  }).join('');
  document.getElementById('exampleCard').innerHTML =
    '<article class="pcard">' +
      '<div class="pcard-read">' +
        '<div class="pcard-top">' +
          '<span class="badge ' + sm.cls + '">' + sm.label + '</span>' +
          diffBadge(p.difficulty) +
        '</div>' +
        '<div class="prompt' + reviewClass(p, 'prompt') + '">' + fmtText(glossedPrompt(p)) + '</div>' +
        renderDiagrams(p.diagrams, p) +
      '</div>' +
      '<div class="pcard-work">' +
        sub +
        '<div class="soltpl mono' + reviewClass(p, 'solutionTemplate') + '">' + renderMath(p.solutionTemplate) + '</div>' +
        '<div class="answers' + reviewClass(p, 'blanks') + '">' + answers + '</div>' +
        (p.expectedOutput ?
          '<div class="expected-lock">' + (singleBlank ? '빈칸 답을 펼치면' : '빈칸 답을 모두 펼치면') + ' 최종 답이 표시됩니다.</div>' +
          '<div class="expected' + reviewClass(p, 'expectedOutput') + '" hidden><span>최종 답</span><b class="mono">' + fmtText(p.expectedOutput) + '</b></div>' : '') +
      '</div>' +
    '</article>';
  var answerDetails = document.querySelectorAll('#exampleCard .answers details');
  var expected = document.querySelector('#exampleCard .expected');
  var lock = document.querySelector('#exampleCard .expected-lock');
  function syncExpected(){
    var done = Array.prototype.every.call(answerDetails, function(d){ return d.open; });
    if(expected) expected.hidden = !done;      // 최종 답이 빈 문항은 두 칸이 아예 없다
    if(lock) lock.hidden = done;
  }
  function syncInlineBlank(detail){
    var id = detail.id.replace('ex-ans-', '');
    var blank = blankById[id];
    if(!blank) return;
    document.querySelectorAll('#exampleCard .blankbtn[data-blank-id="' + id + '"]').forEach(function(btn){
      btn.classList.toggle('filled', detail.open);
      btn.title = detail.open ? '정답 숨기기' : '정답 보기';
      btn.innerHTML = detail.open ? renderMath(blank.answer) : '___';
    });
  }
  answerDetails.forEach(function(d){
    d.addEventListener('toggle', function(){
      syncInlineBlank(d);
      syncExpected();
    });
  });
  syncExpected();
  document.getElementById('exampleCounter').textContent = (exampleIndex + 1) + ' / ' + deck.length;
  document.getElementById('exampleDots').innerHTML = deck.map(function(_, i){
    return '<button class="stepper-dot' + (i === exampleIndex ? ' current' : '') + '" data-i="' + i + '" title="예제 ' + (i+1) + '"></button>';
  }).join('');
  var nextBtn = document.getElementById('exampleNextBtn');
  nextBtn.textContent = returnsToTheory() ? (nextTheorySection(exampleReturnSection) ? '이론으로 →' : lastCardLabel('example', 'derivation', '유도로 →'))
    : (exampleIndex === deck.length - 1)
      ? lastCardLabel('example', 'derivation', '유도로 →') : '다음 →';
}
var exampleReturnSection = null;
function nextTheorySection(sid){
  var inRange = (typeof sectionInRange === 'function') ? sectionInRange : function(){ return true; };
  var secs = passSections().filter(function(s){ return !isChapterSummary(s) && (s.id === sid || inRange(s.id)); });
  var at = secs.findIndex(function(s){ return s.id === sid; });
  return at >= 0 ? secs[at + 1] || null : null;
}
function returnsToTheory(){
  if(!exampleReturnSection) return false;
  var deck = exampleDeck(), cur = deck[exampleIndex], nxt = deck[exampleIndex + 1];
  return !!cur && cur.section === exampleReturnSection && (!nxt || nxt.section !== cur.section);
}
function backToTheory(sid, after){
  if(after && !nextTheorySection(sid)){
    exampleReturnSection = null;
    var next = nextVisiblePage('example');
    startFromTop(next); showPage(next); return;
  }
  var secs = passSections(), at = -1;
  for(var i = 0; i < secs.length; i++){ if(secs[i].id === sid) at = i; }
  var target = null;
  if(after){
    target = (at >= 0 && secs[at + 1]) ? document.getElementById('theory-' + secs[at + 1].id)
      : document.getElementById('theoryNextBtn');
  } else {
    var host = document.getElementById('theory-' + sid);
    target = host && (host.querySelector('.pass-flow') || host);
  }
  exampleReturnSection = null;
  showPage('theory');
  if(target) scrollCardToReadingPosition(target, 0.12);
}
document.getElementById('exampleDots').addEventListener('click', function(e){
  var dot = e.target.closest('.stepper-dot');
  if(!dot) return;
  exampleReturnSection = null;
  exampleIndex = Number(dot.getAttribute('data-i'));
  renderExampleCard();
  scrollCardToReadingPosition(document.querySelector('#exampleCard .pcard'));
});
document.getElementById('examplePrevBtn').addEventListener('click', function(){
  var deck = exampleDeck(), cur = deck[exampleIndex];
  if(exampleReturnSection && cur && cur.section === exampleReturnSection
     && (exampleIndex === 0 || deck[exampleIndex - 1].section !== cur.section)){
    backToTheory(cur.section, false); return;
  }
  if(exampleIndex === 0){ showPage(previousVisiblePage('example')); return; }
  exampleIndex -= 1;
  renderExampleCard();
  scrollCardToReadingPosition(document.querySelector('#exampleCard .pcard'));
});
document.getElementById('exampleNextBtn').addEventListener('click', function(){
  if(returnsToTheory()){ backToTheory(exampleDeck()[exampleIndex].section, true); return; }
  if(exampleIndex >= exampleDeck().length - 1){
    var afterExample = nextVisiblePage('example');
    startFromTop(afterExample);
    showPage(afterExample); return;
  }
  exampleIndex += 1;
  renderExampleCard();
  scrollCardToReadingPosition(document.querySelector('#exampleCard .pcard'));
});

var probMarks = chapterLearning.probMarks && typeof chapterLearning.probMarks === 'object'
  ? chapterLearning.probMarks : {};  // qid -> 'o' | 'tri' | 'x'
var oxPicks = chapterLearning.oxPicks && typeof chapterLearning.oxPicks === 'object'
  ? chapterLearning.oxPicks : {};  // qid -> true(O) | false(X), OX형 문항 전용(2026-09-05)
var shuffleOn = viewerSettings.shuffleProblems === true;
var wrongOnly = viewerSettings.wrongOnlyProblems === true;
var probOrder = Array.isArray(chapterLearning.probOrder) ? chapterLearning.probOrder : null;

function fisherYates(n){
  var a = [];
  for(var i = 0; i < n; i++) a.push(i);
  for(var i = n - 1; i > 0; i--){
    var j = Math.floor(Math.random() * (i + 1));
    var t = a[i]; a[i] = a[j]; a[j] = t;
  }
  return a;
}
function validProblemOrder(order, n){
  if(!Array.isArray(order) || order.length !== n) return false;
  var seen = {};
  for(var i = 0; i < order.length; i++){
    if(!Number.isInteger(order[i]) || order[i] < 0 || order[i] >= n || seen[order[i]]) return false;
    seen[order[i]] = true;
  }
  return true;
}
if(shuffleOn){
  if(!validProblemOrder(probOrder, (CH.problems || []).length)) probOrder = fisherYates((CH.problems || []).length);
} else {
  probOrder = null;
}
function syncProbTools(){
  var sh = document.getElementById('shuffleBtn'), wr = document.getElementById('wrongOnlyBtn');
  sh.classList.toggle('on', shuffleOn);
  sh.textContent = '섞기: ' + (shuffleOn ? '켜짐' : '꺼짐');
  wr.classList.toggle('on', wrongOnly);
  wr.textContent = '△·X만 보기: ' + (wrongOnly ? '켜짐' : '꺼짐');
}
var EXAM_DEFAULT_MINUTES = 75;
var EXAM_POINTS_PER_PROBLEM = 4;
function examMinutesText(){
  var m = Number(CH.examMinutes) || EXAM_DEFAULT_MINUTES;
  var h = Math.floor(m / 60), r = m % 60;
  return (h ? h + '시간' : '') + (h && r ? ' ' : '') + (r ? r + '분' : '');
}
var examAnswers = {};
var examGraded = false;
try { examAnswers = JSON.parse(localStorage.getItem(chapterStoragePrefix + ':exam') || '{}'); }
catch(ignore) { examAnswers = {}; }
function examSave(){
  try { localStorage.setItem(chapterStoragePrefix + ':exam', JSON.stringify(examAnswers)); }
  catch(ignore) {}
}
function examSteps(q){ return (q.exam && q.exam.steps) || []; }
function examIsGraded(st){ return st.type !== 'written'; }
function examPoints(q){
  return examSteps(q).filter(examIsGraded)
                     .reduce(function(s, st){ return s + (st.points || 1); }, 0);
}
function examGet(qid, sid){
  return (examAnswers[qid] || {})[sid];
}
function examSet(qid, sid, v){
  if(!examAnswers[qid]) examAnswers[qid] = {};
  examAnswers[qid][sid] = v;
  examSave();
}
function examGradeStep(q, st){
  var max = st.points || 1, v = examGet(q.id, st.id), got = 0, shown = '';
  if(st.type === 'written'){
    return {got:0, max:0, ok:true, shown:'', written:true};
  }
  if(st.type === 'choice'){
    got = (v === st.answer) ? max : 0;
    shown = st.options[st.answer];
  } else if(st.type === 'ox'){
    got = (v === st.answer) ? max : 0;
    shown = st.answer ? 'O (맞다)' : 'X (틀리다)';
  } else if(st.type === 'number'){
    var want = parseFloat(st.answer), tol = (typeof st.tol === 'number') ? st.tol : Math.abs(want) * 0.005;
    var num = parseFloat(String(v == null ? '' : v).replace(/[^0-9.eE+-]/g, ''));
    got = (isFinite(num) && Math.abs(num - want) <= tol) ? max : 0;
    shown = st.answer + (st.unit ? ' ' + st.unit : '');
  } else if(st.type === 'order' || st.type === 'match'){
    var n = st.answer.length, hit = 0;
    for(var i = 0; i < n; i++){ if(v && v[i] === st.answer[i]) hit++; }
    got = max * hit / n;
    shown = st.answer.map(function(a, i){
      var left = st.type === 'order' ? (i + 1) + '번째' : st.left[i];
      var right = st.type === 'order' ? st.options[a] : st.right[a];
      return left + ' → ' + right;
    }).join(' · ');
  }
  return {got:got, max:max, ok:(got >= max - 1e-9), shown:shown};
}
function examStepBody(q, st){
  var v = examGet(q.id, st.id), qid = esc(q.id), sid = esc(st.id), h = '';
  if(st.type === 'written'){
    return '<div class="exam-written">이 소문제는 <b>손풀이에 적습니다.</b> ' +
      '화면은 채점하지 않고, 채점 뒤 답지의 배점으로 매깁니다.</div>';
  }
  if(st.type === 'choice'){
    h = '<div class="exam-opts">' + st.options.map(function(o, i){
      return '<label class="exam-opt' + (v === i ? ' picked' : '') + '">' +
        '<input type="radio" name="ex-' + qid + '-' + sid + '" value="' + i + '"' +
        (v === i ? ' checked' : '') + (examGraded ? ' disabled' : '') +
        ' data-ex-q="' + qid + '" data-ex-s="' + sid + '" data-ex-kind="choice">' +
        '<span>' + fmtText(o) + '</span></label>';
    }).join('') + '</div>';
  } else if(st.type === 'ox'){
    h = examOxButtons(q, st);
  } else if(st.type === 'number'){
    h = '<input class="exam-num" type="text" inputmode="decimal" autocomplete="off"' +
      ' value="' + esc(v == null ? '' : String(v)) + '"' + (examGraded ? ' disabled' : '') +
      ' data-ex-q="' + qid + '" data-ex-s="' + sid + '" data-ex-kind="number" placeholder="값만">' +
      (st.unit ? '<span class="exam-num-unit">' + esc(st.unit) + '</span>' : '');
  } else if(st.type === 'order'){
    h = '<div class="exam-rows">' + st.options.map(function(o, i){
      var picked = (v && typeof v.indexOf === 'function') ? v.indexOf(i) : -1;
      return '<div class="exam-row"><select' + (examGraded ? ' disabled' : '') +
        ' data-ex-q="' + qid + '" data-ex-s="' + sid + '" data-ex-kind="order" data-ex-i="' + i + '">' +
        '<option value="">순서</option>' +
        st.options.map(function(_, k){
          return '<option value="' + k + '"' + (picked === k ? ' selected' : '') + '>' + (k + 1) + '</option>';
        }).join('') + '</select><span class="exam-row-text">' + fmtText(o) + '</span></div>';
    }).join('') + '</div>';
  } else if(st.type === 'match'){
    h = '<div class="exam-rows">' + st.left.map(function(L, i){
      var picked = (v && v[i] != null) ? v[i] : '';
      return '<div class="exam-row"><span class="exam-row-text">' + fmtText(L) + '</span><select' +
        (examGraded ? ' disabled' : '') +
        ' data-ex-q="' + qid + '" data-ex-s="' + sid + '" data-ex-kind="match" data-ex-i="' + i + '">' +
        '<option value="">고르기</option>' +
        st.right.map(function(R, k){
          return '<option value="' + k + '"' + (picked === k ? ' selected' : '') + '>' + esc(R) + '</option>';
        }).join('') + '</select></div>';
    }).join('') + '</div>';
  }
  return h + examVerdictHtml(q, st);
}
function examVerdictHtml(q, st){
  if(!examGraded) return '';
  var g = examGradeStep(q, st);
  if(g.written) return '';
  return '<div class="exam-verdict ' + (g.ok ? 'ok' : 'no') + '">' +
    (g.ok ? 'O · ' : 'X · ') + '<b>' + fmtNum(g.got) + ' / ' + fmtNum(g.max) + '칸</b> · 정답 ' + fmtText(g.shown) +
    (st.why ? ' — ' + fmtText(st.why) : '') + '</div>' +
    ((st.equations || []).length ? '<div class="exam-eq">' + renderMathLines(st.equations) + '</div>' : '');
}
function examOxButtons(q, st){
  var v = examGet(q.id, st.id), qid = esc(q.id), sid = esc(st.id);
  return '<div class="exam-ox">' + ['O', 'X'].map(function(lab, k){
    var val = (k === 0);
    return '<button type="button" class="exam-ox-btn' + (v === val ? ' picked' : '') + '"' +
      (examGraded ? ' disabled' : '') +
      ' data-ex-q="' + qid + '" data-ex-s="' + sid + '" data-ex-kind="ox" data-ex-v="' + val + '">' +
      lab + '</button>';
  }).join('') + '</div>';
}
function fmtNum(x){ return (Math.round(x * 10) / 10).toString(); }
function examSheetText(){
  var probs = CH.problems || [];
  var lines = [
    '아래 기준으로 내 손풀이를 채점해줘. 풀이는 사진으로 함께 보낸다.',
    '',
    '[채점 규칙]',
    '· 문항마다 O / △ / X 로 표시하고, 틀린 것만 이유를 자세히 적는다',
    '· 한 문항 ' + EXAM_POINTS_PER_PROBLEM + '점 — 어떤 시각으로 봤나 1점 · 조건을 맞게 짚었나 1점 · 식을 맞게 세웠나 1점 · 최종답 1점',
    '· 최종답 1점은 화면이 이미 매겼다. 나머지 3점을 손풀이에서 매겨 달라 — 답이 틀려도 앞의 셋이 맞으면 3점이다',
    '· 표를 잘못 읽었으면 절반, 접근만 맞으면 4분의 1',
    '· 점수는 관대하게, 틀린 자리는 빠짐없이',
    ''
  ];
  probs.forEach(function(q, i){
    lines.push('[' + (i + 1) + '번] ' + plain(q.prompt));
    lines.push('  정답: ' + plain(renderAnswer(q.answer)));
    examSteps(q).forEach(function(st){
      var g = examGradeStep(q, st);
      lines.push('  ' + plain(st.label) + ' → ' +
        (g.written ? '(손풀이에서 매겨 달라) ' : plain(g.shown) + ' ') +
        (st.why ? '(' + plain(st.why) + ')' : ''));
      (st.equations || []).forEach(function(eq){
        (Array.isArray(eq) ? eq : [eq]).forEach(function(line){
          lines.push('      ' + plain(line));
        });
      });
    });
    lines.push('');
  });
  return lines.join('\n');
}
function plain(s){
  return String(s == null ? '' : s)
    .replace(/<[^>]*>/g, '')
    .replace(/\\d?frac\{((?:[^{}]|\{[^{}]*\})*)\}\{((?:[^{}]|\{[^{}]*\})*)\}/g, '($1)/($2)')
    .replace(/\\[a-zA-Z]+/g, '')
    .replace(/\\\(|\\\)|[{}]/g, '')
    .replace(/\*\*/g, '').replace(/\s+/g, ' ').trim();
}
function renderExam(){
  var probs = CH.problems || [];
  if(!probs.length){
    document.getElementById('probList').innerHTML = '<div class="prob-empty">문항이 없습니다.</div>';
    return;
  }
  var total = 0, got = 0, wrong = [];
  probs.forEach(function(q){
    total += examPoints(q);
    examSteps(q).forEach(function(st){
      var g = examGradeStep(q, st);
      got += g.got;
      if(examGraded && !g.ok) wrong.push({q:q, st:st, g:g});
    });
  });
  var head = '<div class="exam-bar">' +
    '<span class="exam-time">시험 시간 ' + examMinutesText() + '</span>' +
    '<span class="exam-bar-note">' + (examGraded
      ? '<b>답만 매긴 점수입니다.</b> 풀이 점수는 아래 답지의 배점으로 손풀이를 채점받습니다.'
      : '<b>답만 적습니다.</b> 풀이는 손으로 풀고, 채점 뒤 답지의 배점(시각 1 · 조건 1 · 식 1 · 답 1)으로 그 손풀이를 매깁니다.') +
    '</span>' +
    (examGraded ? '<button class="exam-btn" id="examReset">다시 풀기</button>' : '') +
    '</div>';
  var score = !examGraded ? '' :
    '<div class="exam-score"><div class="exam-score-big">' + fmtNum(got) + ' / ' + total + '칸 · ' +
      Math.round(got / total * 100) + '% <span class="exam-score-tag">답 기준</span></div>' +
      (wrong.length
        ? '<div class="exam-wrong"><b>틀린 자리 ' + wrong.length + '개</b><ul>' + wrong.map(function(w){
            return '<li>' + esc(w.q.id) + ' · ' + fmtText(w.st.label) +
              (w.st.type === 'ox' && w.st.prompt ? ' ' + fmtText(w.st.prompt) : '') +
              ' — 정답 ' + fmtText(w.g.shown) + '</li>';
          }).join('') + '</ul></div>'
        : '<div class="exam-wrong">틀린 자리가 없습니다.</div>') +
    '</div>';
  var cards = probs.map(function(q, i){
    var diagramHtml = renderDiagrams(q.diagrams, q);
    var qGot = examSteps(q).reduce(function(s, st){ return s + examGradeStep(q, st).got; }, 0);
    return '<article class="qcard' + reviewClass(q, 'new') + '" id="q-' + esc(q.id) + '">' +
      '<div class="q-meta">' +
        '<span class="lo-num serif" style="width:auto;">Q' + (i + 1) + '</span>' +
        diffBadge(q.difficulty) +
        '<span class="exam-pts">' + (examGraded ? fmtNum(qGot) + ' / ' : '답 ') + examPoints(q) + '칸</span>' +
      '</div>' +
      '<div class="prompt' + reviewClass(q, 'prompt') + '">' + fmtText(glossedPrompt(q)) + '</div>' +
      diagramHtml +
      examSteps(q).map(function(st){
        if(st.type === 'ox'){
          return '<div class="exam-step">' +
            '<div class="exam-ox-line">' +
              '<div class="exam-ox-text">' +
                (st.label ? '<b>' + fmtText(st.label) + '</b> ' : '') +
                (st.prompt ? fmtText(st.prompt) : '') +
              '</div>' +
              examOxButtons(q, st) +
            '</div>' +
            examVerdictHtml(q, st) +
          '</div>';
        }
        return '<div class="exam-step">' +
          '<div class="exam-step-label">' + fmtText(st.label) + '</div>' +
          (st.prompt ? '<div class="exam-step-prompt">' + fmtText(st.prompt) + '</div>' : '') +
          examStepBody(q, st) +
        '</div>';
      }).join('') +
    '</article>';
  }).join('');
  var sheet = !examGraded ? '' :
    '<details class="exam-sheet" id="examSheet"><summary>답지 시트 — 손풀이를 채점하려면 펼칩니다</summary>' +
    '<div class="exam-sheet-body">' +
      '<p>화면 밖에서 푼 풀이는 <b>이 시트를 캡처해 채팅 AI 에게 함께 보내면</b> 채점받을 수 있습니다. ' +
      '복사가 되는 자리에서는 아래 버튼이 더 정확합니다 — 글자를 그대로 옮기므로 사진을 잘못 읽을 일이 없습니다.</p>' +
      '<button class="exam-btn" id="examCopy">채점 의뢰문 복사</button>' +
      probs.map(function(q, i){
        return '<div class="exam-sheet-q"><b>' + (i + 1) + '번 · ' + EXAM_POINTS_PER_PROBLEM + '점</b>' +
          '<div class="q-ans-val">' + renderAnswer(q.answer) + '</div>' +
          '<div class="q-outline-wrap">' + renderOutline(q.solutionOutline) + '</div></div>';
      }).join('') +
    '</div></details>';
  var submit = examGraded ? '' :
    '<div class="exam-submit">' +
      '<span class="exam-submit-note">채점하면 점수가 맨 위에 뜨고 <b>자가점검 탭이 열립니다.</b></span>' +
      '<button class="exam-btn primary" id="examGrade">채점</button>' +
    '</div>';
  document.getElementById('probList').innerHTML = head + score + cards + submit + sheet;
  wireProblemFigureSlots(probs);
  syncExamGates();
}
function examLocksRecap(){ return !!CH.examMode && !examGraded; }
function passSections(){ return (CH.theory && CH.theory.sections) || []; }
function passSectionDeckIndex(sid){
  var deck = exampleDeck();
  for(var i = 0; i < deck.length; i++){
    if(deck[i].section === sid) return i;
  }
  return -1;
}
function wireSectionFlow(){
  document.querySelectorAll('.pass-flow').forEach(function(el){ el.remove(); });
  passSections().forEach(function(sec){
    var host = document.getElementById('theory-' + sec.id);
    if(!host) return;
    var at = passSectionDeckIndex(sec.id);
    if(at < 0) return;          // 이 절에 걸린 basic 문풀이 아직 없다 — 단추를 만들지 않는다
    var wrap = document.createElement('div');
    wrap.className = 'pass-flow';
    var btn = document.createElement('button');
    btn.className = 'navbtn primary';
    btn.textContent = '이 절 예제 풀기 →';
    btn.addEventListener('click', function(){
      exampleIndex = at;
      exampleReturnSection = sec.id;
      renderExampleCard();
      showPage('example');
      scrollCardToReadingPosition(document.querySelector('#exampleCard .pcard'));
    });
    wrap.appendChild(btn);
    host.appendChild(wrap);
  });
  syncTheoryNext();
}
wireSectionFlow();
function syncExamGates(){
  var tab = document.querySelector('.tabbtn[data-tab="recap"]');
  if(tab){
    tab.classList.toggle('locked', examLocksRecap());
    tab.setAttribute('aria-disabled', String(examLocksRecap()));
    if(examLocksRecap()) tab.setAttribute('title', '채점한 뒤에 열립니다');
    else tab.removeAttribute('title');
  }
  var next = document.getElementById('probNextBtn');
  if(next && CH.examMode) next.hidden = !examGraded;
}
document.getElementById('probList').addEventListener('click', function(e){
  var b = e.target.closest('button');
  if(!b) return;
  if(b.id === 'examGrade'){ examGraded = true; renderExam(); window.scrollTo({top:tabTopScroll(), behavior:'smooth'}); return; }
  if(b.id === 'examReset'){ examGraded = false; examAnswers = {}; examSave(); renderExam(); return; }
  if(b.id === 'examCopy'){
    var txt = examSheetText();
    try {
      navigator.clipboard.writeText(txt).then(function(){ b.textContent = '복사했습니다'; },
        function(){ b.textContent = '복사가 막혔습니다 — 시트를 캡처해 주세요'; });
    } catch(ignore) { b.textContent = '복사가 막혔습니다 — 시트를 캡처해 주세요'; }
    return;
  }
  if(b.classList.contains('exam-ox-btn')){
    var oxY = window.scrollY;
    examSet(b.getAttribute('data-ex-q'), b.getAttribute('data-ex-s'), b.getAttribute('data-ex-v') === 'true');
    renderExam();
    window.scrollTo(0, oxY);
  }
});
document.getElementById('probList').addEventListener('change', function(e){
  var el = e.target, kind = el.getAttribute && el.getAttribute('data-ex-kind');
  if(!kind) return;
  var qid = el.getAttribute('data-ex-q'), sid = el.getAttribute('data-ex-s');
  if(kind === 'choice'){ examSet(qid, sid, parseInt(el.value, 10)); renderExam(); }
  else if(kind === 'order' || kind === 'match'){
    var i = parseInt(el.getAttribute('data-ex-i'), 10);
    var cur = examGet(qid, sid);
    cur = Array.isArray(cur) ? cur.slice() : [];
    if(kind === 'order'){
      var pos = el.value === '' ? -1 : parseInt(el.value, 10);
      for(var k = 0; k < cur.length; k++) if(cur[k] === i) cur[k] = undefined;
      if(pos >= 0) cur[pos] = i;
    } else {
      cur[i] = el.value === '' ? undefined : parseInt(el.value, 10);
    }
    examSet(qid, sid, cur);
  }
});
document.getElementById('probList').addEventListener('input', function(e){
  var el = e.target;
  if(el.getAttribute && el.getAttribute('data-ex-kind') === 'number'){
    examSet(el.getAttribute('data-ex-q'), el.getAttribute('data-ex-s'), el.value);
  }
});

function renderProblems(){
  if(CH.examMode){ renderExam(); return; }
  var probs = CH.problems || [];
  var idxs = [];
  if(shuffleOn && probOrder){ idxs = probOrder.slice(); }
  else { for(var i = 0; i < probs.length; i++) idxs.push(i); }
  idxs = idxs.filter(function(i){ return itemInRange(probs[i]); });
  if(wrongOnly){
    idxs = idxs.filter(function(i){
      var m = probMarks[probs[i].id];
      return m === 'tri' || m === 'x';
    });
  }
  if(!idxs.length){
    document.getElementById('probList').innerHTML =
      '<div class="prob-empty">' + (wrongOnly ? '△·X로 표시한 문제가 없습니다. 자가 채점을 먼저 해보세요.' : '문제가 없습니다.') + '</div>';
    return;
  }
  document.getElementById('probList').innerHTML = idxs.map(function(i){
    var q = probs[i];
    var outline = renderOutline(q.solutionOutline);
    var diagramHtml = renderDiagrams(q.diagrams, q);
    var solutionDiagramHtml = renderDiagrams(q.solutionDiagrams, q);
    var solutionFigure = diagramHtml && q.figureMode === 'solution';
    var figureBlock = (!diagramHtml || solutionFigure) ? '' : q.figureMode === 'given' ? diagramHtml
      : '<details class="q-fig-hint"><summary>삽화 힌트 – 모델링이 안 세워지면 펼치기</summary>' + diagramHtml + '</details>';
    var solutionFigureHtml = (solutionFigure ? '<div class="q-fig-solution">' + diagramHtml + '</div>' : '') +
      (solutionDiagramHtml ? '<div class="q-fig-solution">' + solutionDiagramHtml + '</div>' : '');
    var hasSolutionFigure = !!solutionFigureHtml;
    var mk = probMarks[q.id];
    var isOx = typeof q.oxCorrect === 'boolean';
    var answerBlock;
    if(isOx){
      var oxPicked = oxPicks[q.id];   // true(O) | false(X) | undefined(안 누름)
      var oxJudged = typeof oxPicked === 'boolean';
      answerBlock = '<div class="exam-ox" style="margin-top:12px;">' + ['O', 'X'].map(function(lab, k){
        var val = (k === 0);
        return '<button type="button" class="exam-ox-btn' + (oxPicked === val ? ' picked' : '') + '"' +
          ' data-oxq="' + esc(q.id) + '" data-oxv="' + val + '">' + lab + '</button>';
      }).join('') + '</div>' +
      (!oxJudged ? '' :
        '<div class="exam-verdict ' + (oxPicked === q.oxCorrect ? 'ok' : 'no') + '">' +
          (oxPicked === q.oxCorrect ? '정답입니다.' : '오답입니다.') +
        '</div>' +
        '<div class="q-ans-val' + reviewClass(q, 'answer') + '">' + renderAnswer(q.answer) + '</div>' +
        solutionFigureHtml +
        '<div class="q-outline-wrap' + reviewClass(q, 'solutionOutline') + '">' + outline + '</div>');
    } else {
      answerBlock = '<details class="q-answer">' +
        '<summary>정답 · 풀이 뼈대 펼치기 (먼저 스스로 푼 다음에)</summary>' +
        '<div class="q-ans-val' + reviewClass(q, 'answer') + '">' + renderAnswer(q.answer) + '</div>' +
        solutionFigureHtml +
        '<div class="q-outline-wrap' + reviewClass(q, 'solutionOutline') + '">' + outline + '</div>' +
      '</details>' +
      '<div class="selfmark"><span class="selfmark-label">자가 채점</span>' +
        '<button class="mark-btn' + (mk === 'o' ? ' sel-o' : '') + '" data-q="' + esc(q.id) + '" data-m="o" title="맞음">O</button>' +
        '<button class="mark-btn' + (mk === 'tri' ? ' sel-tri' : '') + '" data-q="' + esc(q.id) + '" data-m="tri" title="찝찝함">△</button>' +
        '<button class="mark-btn' + (mk === 'x' ? ' sel-x' : '') + '" data-q="' + esc(q.id) + '" data-m="x" title="틀림">X</button>' +
      '</div>';
    }
    return '<article class="qcard' + (hasSolutionFigure ? ' has-solution-figure' : '') + reviewClass(q, 'new') + '" id="q-' + esc(q.id) + '">' +
      '<div class="q-meta">' +
        '<span class="lo-num serif" style="width:auto;">Q' + (i+1) + '</span>' +
        diffBadge(q.difficulty) +
        (isOx ? '<span class="badge ox-kind">O, X 문제</span>' : '') +
      '</div>' +
      '<div class="prompt' + reviewClass(q, 'prompt') + '">' + fmtText(glossedPrompt(q)) + '</div>' +
      figureBlock +
      answerBlock +
    '</article>';
  }).join('');
  wireProblemFigureSlots(idxs.map(function(i){ return probs[i]; }));
}
function wireProblemFigureSlots(shown){
  shown.forEach(function(q){
    var slots = q.figureSlots || [];
    if(!slots.length) return;
    var card = document.getElementById('q-' + q.id);
    if(!card) return;
    var det = card.querySelector('.q-answer');
    if(!det) return;
    function sync(){
      slots.forEach(function(s){
        var el = card.querySelector('[id="' + s.slot + '"]');
        if(!el) return;
        el.textContent = det.open ? s.value : '?';
        el.classList.toggle('filled-answer-slot', det.open);
      });
      if(det.open) revealConditionsIn(card);                                   // W-36
    }
    det.addEventListener('toggle', function(){
      if(det.open){
        var hint = card.querySelector('.q-fig-hint');
        if(hint) hint.open = true;
      }
      sync();
    });
    sync();
  });
}
document.getElementById('probList').addEventListener('click', function(e){
  var ob = e.target.closest('[data-oxq]');
  if(ob){
    var oxq = ob.getAttribute('data-oxq');
    var oxv = (ob.getAttribute('data-oxv') === 'true');
    var oxCard = ob.closest('.qcard');
    var beforeTop = oxCard ? oxCard.getBoundingClientRect().top : null;
    oxPicks[oxq] = (oxPicks[oxq] === oxv) ? undefined : oxv;  // 같은 버튼 다시 누르면 해제
    saveChapterLearning();
    renderProblems();
    var reanchor = function(){
      var card = document.getElementById('q-' + oxq);
      if(!card || beforeTop === null) return;
      var diff = card.getBoundingClientRect().top - beforeTop;
      if(Math.abs(diff) > 0.5) window.scrollBy(0, diff);
    };
    reanchor();
    setTimeout(reanchor, 0);
    return;
  }
  var mb = e.target.closest('.mark-btn');
  if(!mb) return;
  var qid = mb.getAttribute('data-q'), m = mb.getAttribute('data-m');
  probMarks[qid] = (probMarks[qid] === m) ? undefined : m;  // 같은 버튼 다시 누르면 해제
  saveChapterLearning();
  mb.parentElement.querySelectorAll('.mark-btn').forEach(function(b){
    b.classList.remove('sel-o', 'sel-tri', 'sel-x');
  });
  if(probMarks[qid]) mb.classList.add({o:'sel-o', tri:'sel-tri', x:'sel-x'}[m]);
});
document.getElementById('shuffleBtn').addEventListener('click', function(){
  shuffleOn = !shuffleOn;
  probOrder = shuffleOn ? fisherYates((CH.problems || []).length) : null;  // 켤 때마다 새로 섞는다
  updateViewerSettings({shuffleProblems:shuffleOn});
  saveChapterLearning();
  syncProbTools();
  renderProblems();
});
document.getElementById('wrongOnlyBtn').addEventListener('click', function(){
  wrongOnly = !wrongOnly;
  updateViewerSettings({wrongOnlyProblems:wrongOnly});
  syncProbTools();
  renderProblems();
});

var savedReaderPosition = null;
try { if('scrollRestoration' in history) history.scrollRestoration = 'manual'; } catch(ignore) {}
try { savedReaderPosition = JSON.parse(localStorage.getItem(chapterStoragePrefix + ':scroll') || 'null'); } catch(ignore) {}
if(savedReaderPosition){
  if(Number.isInteger(savedReaderPosition.prac) && savedReaderPosition.prac >= 0 && savedReaderPosition.prac < pracDeck().length){
    pracIndex = savedReaderPosition.prac;
  }
  if(Number.isInteger(savedReaderPosition.deriv) && savedReaderPosition.deriv >= 0 && savedReaderPosition.deriv < CH.derivation.formulas.length){
    derivIndex = savedReaderPosition.deriv;
  }
  if(Number.isInteger(savedReaderPosition.example) && savedReaderPosition.example >= 0 && savedReaderPosition.example < exampleDeck().length){
    exampleIndex = savedReaderPosition.example;
  }
}
applyProgress(false);
var XSCROLL_SEL = '.fmath,.fmath-col,.steq,.steq-chain';
var xscrollRO = window.ResizeObserver ? new ResizeObserver(function(){ queueXScroll(); }) : null;
function syncXScroll(){
var EQ_REL = /[=<>≤≥≈≅]/;
var EQ_NBSP = String.fromCharCode(160);
function breakBeforeEquals(root){
  var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
  var nodes = [], n;
  while((n = w.nextNode())) nodes.push(n);
  var relAfter = new RegExp(EQ_NBSP + '(?=[=<>≤≥≈≅])', 'g');
  var commaAfter = new RegExp(',' + EQ_NBSP, 'g');
  for(var i = 0; i < nodes.length; i++){
    var v = nodes[i].nodeValue;
    if(v.indexOf(' ') < 0) continue;
    v = v.split(' ').join(EQ_NBSP);
    v = v.replace(relAfter, ' ');
    v = v.replace(commaAfter, ', ');
    nodes[i].nodeValue = v;
  }
  for(var j = 0; j + 1 < nodes.length; j++){
    var next = nodes[j + 1].nodeValue;
    if(EQ_REL.test(next.charAt(0)) && nodes[j].nodeValue.slice(-1) === EQ_NBSP){
      nodes[j].nodeValue = nodes[j].nodeValue.slice(0, -1) + ' ';
    }
  }
}
  var nodes = document.querySelectorAll(XSCROLL_SEL);
  for(var i = 0; i < nodes.length; i++){
    var el = nodes[i];
    if(!el.dataset.eqbrk){ el.dataset.eqbrk = '1'; breakBeforeEquals(el); }
    el.classList.toggle('has-xscroll', el.scrollWidth - el.clientWidth > 1);
    if(xscrollRO && !el.dataset.xro){ el.dataset.xro = '1'; xscrollRO.observe(el); }
  }
}
var xscrollQueued = false;
function queueXScroll(){
  if(xscrollQueued) return;
  xscrollQueued = true;
  setTimeout(function(){ xscrollQueued = false; syncXScroll(); }, 0);
}
window.addEventListener('resize', queueXScroll, {passive:true});
window.addEventListener('load', queueXScroll);
if(document.fonts && document.fonts.ready){ document.fonts.ready.then(queueXScroll); }
if(window.MutationObserver){
  new MutationObserver(queueXScroll).observe(document.body, {childList:true, subtree:true});
}

function initStep(label, fn){
  try { fn(); }
  catch(err){ console.error('[viewer] 초기화 실패: ' + label + ' — 나머지 화면은 계속 그립니다', err); }
}
initStep('example', renderExampleCard);
initStep('derivation', renderDerivCard);
initStep('practice', renderPracCard);
initStep('problems tools', syncProbTools);
initStep('problems', renderProblems);
initStep('recap picks', syncRecapPicks);
initStep('recap status', updateRecapStatus);
initStep('review tools', syncReviewTools);
initStep('review cursor', restoreReviewCursor);
initStep('review note fold', startReviewNoteFold);
initStep('save learning', saveChapterLearning);
function stripOneTimeNavParams(){
  try {
    var url = new URL(window.location.href);
    url.searchParams.delete('start');
    url.searchParams.delete('review');
    history.replaceState(history.state, '', url.pathname + url.search + url.hash);
  } catch(ignore) {}
}
var DEEP_LINK_HASH = /^#([A-Za-z][A-Za-z0-9_-]*)$/;
var deepLink = DEEP_LINK_HASH.exec(window.location.hash);
var deepLinkTarget = deepLink && document.getElementById(deepLink[1]);
if(openFormulaHash(window.location.hash)){
  armCrossChapterBack();
} else if(deepLinkTarget){
  var host = deepLinkTarget.closest('.page[data-page]');
  showPage(host ? host.getAttribute('data-page') : 'theory');
  armCrossChapterBack();
  var deepLinkUserScrolled = false;
  var onUserScroll = function(){ deepLinkUserScrolled = true; window.removeEventListener('wheel', onUserScroll); window.removeEventListener('touchmove', onUserScroll); window.removeEventListener('keydown', onUserScroll); };
  window.addEventListener('wheel', onUserScroll, {passive:true});
  window.addEventListener('touchmove', onUserScroll, {passive:true});
  window.addEventListener('keydown', onUserScroll);
  var landDeepLink = function(){ if(!deepLinkUserScrolled) deepLinkTarget.scrollIntoView({block:'start'}); };
  requestAnimationFrame(landDeepLink);
  if(document.fonts && document.fonts.ready){ document.fonts.ready.then(landDeepLink); }
  window.addEventListener('load', function(){ requestAnimationFrame(landDeepLink); });
} else if(/[?&]review=(first|last)(?:&|$)/.test(window.location.search)){
  (function(){
    var wantLast = /[?&]review=last(?:&|$)/.test(window.location.search);
    stripOneTimeNavParams();
    if(!reviewEnabled){
      reviewEnabled = true;
      updateViewerSettings({reviewHighlights:reviewEnabled});
      syncReviewTools();
    }
    var plan = reviewPlan();
    if(!plan.length){
      var hop = reviewAdjacentChapter(wantLast ? -1 : 1);
      if(hop){ window.location.replace(hop + '?review=' + (wantLast ? 'last' : 'first')); return; }
      showPage('lo'); window.scrollTo(0, 0);
      reviewAnnounce('더 볼 변경점이 없습니다 — 마지막 장입니다.');
      return;
    }
    reviewNavIndex = wantLast ? plan.length - 1 : 0;
    reviewNavLanded = true;                 // 넘어온 것 자체가 '착지'다 — 한 번 더 누르게 하지 않는다
    syncReviewNavigation();
    var target = reviewShowPlanEntry(plan[reviewNavIndex]);
    if(target) scrollReviewTargetIntoView(target);
  })();
} else if(/[?&]start=lo(?:&|$)/.test(window.location.search)){
  stripOneTimeNavParams();
  showPage('lo');
  window.scrollTo(0, 0);
  requestAnimationFrame(function(){ window.scrollTo(0, 0); });
} else {
  var restorePage = savedReaderPosition && savedReaderPosition.page;
  var canRestore = restorePage
    && document.querySelector('.page[data-page="' + restorePage + '"]')
    && hiddenPages.indexOf(restorePage) === -1;
  showPage(canRestore ? restorePage : 'lo');
  if(savedReaderPosition && Number.isFinite(savedReaderPosition.y)){
    requestAnimationFrame(function(){ window.scrollTo(0, savedReaderPosition.y); });
  } else {
    requestAnimationFrame(function(){ window.scrollTo(0, 0); });
  }
}

(function(){
  var T = (typeof CH === 'object' && CH && CH.tutorial) || null;
  var steps = (T && T.steps) || [];
  if(!steps.length) return;
  window.TUTORIAL = {
    key: (CH.subject || '') + ':' + (CH.chapterNumber || '') + ':' + (T.id || 'x'),
    steps: steps
  };
})();
