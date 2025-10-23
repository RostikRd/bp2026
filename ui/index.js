// Autosize textarea, hotkeys, copy with toast, scroll behaviors
(function(){
  const ta = document.getElementById('input');
  const form = document.getElementById('composer');
  const toast = document.getElementById('toast');
  const messages = document.getElementById('messages');
  const sidebar = document.querySelector('.sidebar');
  const backdrop = document.getElementById('backdrop');

  function autosize(){
    if(!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, window.innerHeight * 0.4) + 'px';
  }
  ta && ['input','change'].forEach(e=>ta.addEventListener(e, autosize));
  autosize();

  // Submit: Ctrl/Cmd+Enter to send
  ta && ta.addEventListener('keydown', (e)=>{
    if((e.ctrlKey || e.metaKey) && e.key === 'Enter'){
      form.requestSubmit();
    }
  });

  form && form.addEventListener('submit', (e)=>{
    e.preventDefault();
    if(!ta || !ta.value.trim()) return;
    const article = document.createElement('article');
    article.className = 'message message--user';
    const bubble = document.createElement('div');
    bubble.className = 'message__bubble';
    bubble.textContent = ta.value.trim();
    article.appendChild(bubble);
    messages.appendChild(article);
    ta.value=''; autosize();
    messages.scrollTop = messages.scrollHeight;
  });

  // Sidebar toggle on mobile
  document.querySelectorAll('[data-sidebar-toggle]').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      if(!sidebar) return;
      const open = sidebar.classList.toggle('is-open');
      if(backdrop){ backdrop.hidden = !open; backdrop.onclick = ()=>{ sidebar.classList.remove('is-open'); backdrop.hidden = true; }; }
    });
  });

  // Simple infinite scroll mock: add skeleton when reaching top
  let loading = false;
  messages && messages.addEventListener('scroll', ()=>{
    if(loading) return;
    if(messages.scrollTop <= 0){
      loading = true;
      const sk = document.createElement('div');
      sk.className = 'message';
      sk.innerHTML = '<div class="message__bubble" style="height:64px;background:linear-gradient(90deg,#12202c,#10161f,#12202c);background-size:200% 100%;animation:shimmer 1.2s infinite;"></div>';
      messages.prepend(sk);
      setTimeout(()=>{ sk.remove(); loading = false; }, 900);
    }
  });

  // Copy buttons
  document.querySelectorAll('[data-copy]').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const sel = btn.getAttribute('data-copy');
      const src = document.querySelector(sel);
      if(!src) return;
      try{
        await navigator.clipboard.writeText(src.textContent || '');
        showToast('Copied');
      }catch(err){ showToast('Copy failed'); }
    });
  });

  function showToast(text){
    if(!toast) return;
    toast.textContent = text;
    toast.hidden = false;
    toast.classList.add('is-show');
    setTimeout(()=>{ toast.classList.remove('is-show'); toast.hidden = true; }, 1400);
  }
})();

// Keyframes for shimmer
const style = document.createElement('style');
style.textContent = '@keyframes shimmer{0%{background-position:0 0}100%{background-position:200% 0}}';
document.head.appendChild(style);

console.log('Happy developing ✨')
