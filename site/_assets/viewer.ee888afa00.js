
(function(){
  var T = (typeof window.TUTORIAL === 'object' && window.TUTORIAL) || null;
  var steps = (T && T.steps) || [];
  if(!steps.length) return;
  var KEY = 'tut:' + (T.key || 'x');
  var hole = null, box = null, at = 0, live = [];

  function seen(){ try { return localStorage.getItem(KEY) === '1'; } catch(e){ return false; } }
  function markSeen(){ try { localStorage.setItem(KEY, '1'); } catch(e){} }

  function pageOf(el){ return el.closest ? el.closest('.page[data-page]') : null; }
  function ensureVisible(el){
    var page = pageOf(el);
    if(page && !page.classList.contains('active') && typeof showPage === 'function'){
      showPage(page.getAttribute('data-page'));
    }
  }

  function resolve(){
    live = [];
    steps.forEach(function(s, i){
      var el = (s && s.target) ? document.querySelector(s.target) : null;
      var page = el ? pageOf(el) : null;
      if(el && page && typeof hiddenPages !== 'undefined'
         && hiddenPages.indexOf(page.getAttribute('data-page')) !== -1){
        console.warn('[튜토리얼] 숨긴 탭의 대상이라 건너뛴다 — 단계 ' + (i + 1) + ': ' + s.target);
        return;
      }
      if(el) live.push({ el: el, text: (s && s.text) || '' });
      else console.warn('[튜토리얼] 대상을 못 찾았다 — 단계 ' + (i + 1) + ': ' + (s && s.target));
    });
    return live.length;
  }

  function place(){
    var it = live[at]; if(!it || !hole || !box) return;
    var r = it.el.getBoundingClientRect(), pad = 6;
    hole.style.top = (r.top - pad) + 'px';
    hole.style.left = (r.left - pad) + 'px';
    hole.style.width = (r.width + pad * 2) + 'px';
    hole.style.height = (r.height + pad * 2) + 'px';
    var y = r.bottom + 12;
    if(y + box.offsetHeight > window.innerHeight - 12) y = Math.max(12, r.top - box.offsetHeight - 12);
    box.style.top = y + 'px';
    box.style.left = Math.max(12, Math.min(r.left, window.innerWidth - box.offsetWidth - 12)) + 'px';
  }

  function render(){
    var it = live[at];
    box.innerHTML = '';
    var p = document.createElement('p'); p.textContent = it.text; box.appendChild(p);
    var row = document.createElement('div'); row.className = 'tut-actions';
    var n = document.createElement('span'); n.className = 'tut-count';
    n.textContent = (at + 1) + ' / ' + live.length; row.appendChild(n);
    var quit = document.createElement('button'); quit.type = 'button';
    quit.className = 'tut-quit'; quit.textContent = '그만 보기';
    quit.addEventListener('click', close); row.appendChild(quit);
    if(at > 0){
      var prev = document.createElement('button'); prev.type = 'button'; prev.textContent = '이전';
      prev.addEventListener('click', function(){ at--; step(); }); row.appendChild(prev);
    }
    var next = document.createElement('button'); next.type = 'button';
    next.textContent = (at === live.length - 1) ? '끝' : '다음';
    next.addEventListener('click', function(){
      if(at === live.length - 1) close(); else { at++; step(); }
    });
    row.appendChild(next);
    box.appendChild(row);
  }

  function step(){
    if(!live[at]) return close();
    ensureVisible(live[at].el);            // 다른 탭이면 그 탭을 먼저 연다 (안 그러면 구멍이 0×0 이다)
    live[at].el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    render();
    requestAnimationFrame(place);
    setTimeout(place, 260);
  }

  function onKey(e){ if(e.key === 'Escape') close(); }

  function open(){
    if(hole || !resolve()) return;
    at = 0;
    hole = document.createElement('div'); hole.className = 'tut-hole';
    box = document.createElement('div'); box.className = 'tut-box';
    document.body.appendChild(hole); document.body.appendChild(box);
    document.addEventListener('keydown', onKey);
    window.addEventListener('scroll', place, { passive: true });
    window.addEventListener('resize', place);
    step();
  }

  function close(){
    markSeen();
    document.removeEventListener('keydown', onKey);
    window.removeEventListener('scroll', place);
    window.removeEventListener('resize', place);
    if(hole && hole.parentNode) hole.parentNode.removeChild(hole);
    if(box && box.parentNode) box.parentNode.removeChild(box);
    hole = null; box = null;
  }

  var host = document.querySelector('[data-tut-host]');
  if(host){
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'tut-replay'; b.textContent = '설명 다시 보기';
    b.addEventListener('click', open);
    host.appendChild(b);
  }
  if(!seen()) setTimeout(open, 400);
})();
