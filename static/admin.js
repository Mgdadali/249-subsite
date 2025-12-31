// admin.js
async function loadClients(){
  const el = document.getElementById('clientsList');
  el.innerHTML = 'جاري التحميل...';
  try{
    const res = await fetch('/admin/api/clients');
    if(!res.ok) throw new Error('unauth');
    const list = await res.json();
    if(!list.length) { el.innerHTML = '<p class="muted">لا يوجد عملاء مضافين</p>'; return; }
    el.innerHTML = '';
    list.forEach(c => {
      const btn = document.createElement('button');
      btn.className = 'client-item';
      btn.textContent = `${c.name} — ${c.code}`;
      btn.onclick = ()=> loadClientDetails(c.code);
      el.appendChild(btn);
    });
  }catch(err){
    el.innerHTML = '<p style="color:#c00">خطأ في جلب بيانات العملاء</p>';
    console.error(err);
  }
}

async function loadClientDetails(code){
  const panel = document.getElementById('clientPanel');
  panel.innerHTML = 'جاري تحميل بيانات العميل...';
  try{
    const res = await fetch(`/admin/api/client/${encodeURIComponent(code)}/checklist`);
    const data = await res.json();
    if(data.error){ panel.innerHTML = `<p class="muted">${data.error}</p>`; return; }

    // header
    panel.innerHTML = `<h3>العميل: ${code}</h3><p class="muted">المراحل التالية:</p>`;

    // actions
    panel.innerHTML += `<div style="margin:10px 0"><button onclick="openAddClient('${code}')" class="admin-small-btn">➕ إضافة مرحلة</button></div>`;

    // list
    const ul = document.createElement('ul');
    ul.className = 'checklist-list';
    data.steps.forEach(s=>{
      const li = document.createElement('li');
      li.className = s.done ? 'done' : '';
      li.innerHTML = `
        <div class="step-left">
          <div class="step-badge">•</div>
          <div class="step-text"><strong>${s.name}</strong></div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <button class="admin-action" onclick="toggleStep('${code}','${escapeJs(s.name)}', this)">${s.done ? 'إلغاء ✅' : 'تعيين ✅'}</button>
          <button class="admin-action danger" onclick="deleteStep('${code}','${escapeJs(s.name)}', this)">حذف 🗑️</button>
        </div>
      `;
      ul.appendChild(li);
    });
    panel.appendChild(ul);
  }catch(err){
    panel.innerHTML = '<p style="color:#c00">حدث خطأ أثناء تحميل بيانات العميل</p>';
    console.error(err);
  }
}

function escapeJs(str){
  return str.replace(/'/g,"\\'").replace(/"/g,'\\"');
}

async function toggleStep(code, step, btn){
  try{
    btn.disabled = true;
    const res = await fetch(`/admin/api/client/${encodeURIComponent(code)}/toggle-step`, {
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({step})
    });
    const data = await res.json();
    if(data.ok) loadClientDetails(code);
    else alert('خطأ: ' + (data.error||''));
  }catch(e){ console.error(e); alert('خطأ في الشبكة'); }
  finally{ btn.disabled = false; }
}

async function deleteStep(code, step, btn){
  if(!confirm('هل متأكد من حذف هذه المرحلة؟')) return;
  try{
    btn.disabled = true;
    const res = await fetch(`/admin/api/client/${encodeURIComponent(code)}/delete-step`, {
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({step})
    });
    const data = await res.json();
    if(data.ok) loadClientDetails(code);
    else alert('خطأ: ' + (data.error||''));
  }catch(e){ console.error(e); alert('خطأ في الشبكة'); }
  finally{ btn.disabled = false; }
}


// فتح نافذة إضافة عميل/مرحلة بسيطة
function openAddClient(code){
  const modalHtml = `
    <div style="padding:12px">
      <h4>${code ? 'إضافة مرحلة للعميل ' + code : 'إضافة عميل جديد'}</h4>
      <div style="margin-top:8px">
        ${code ? `<input id="newStep" placeholder="اسم المرحلة">` : `<input id="newName" placeholder="اسم العميل"><br><br><input id="newService" placeholder="الخدمة">`}
        <div style="margin-top:10px">
          <button onclick="submitAdd('${code||''}')">حفظ</button>
          <button onclick="closeModal()">إلغاء</button>
        </div>
      </div>
    </div>
  `;
  showModal(modalHtml);
}

function showModal(html){
  let overlay = document.getElementById('adminModal');
  if(!overlay){
    overlay = document.createElement('div');
    overlay.id = 'adminModal';
    overlay.style = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;z-index:9999;';
    document.body.appendChild(overlay);
  }
  overlay.innerHTML = `<div style="background:#fff;padding:18px;border-radius:10px;max-width:480px;width:100%;">${html}</div>`;
}

function closeModal(){
  const overlay = document.getElementById('adminModal');
  if(overlay) overlay.remove();
}

async function submitAdd(code){
  if(code){
    // add step for code
    const step = document.getElementById('newStep').value.trim();
    if(!step){ alert('اكتب اسم المرحلة'); return; }
    // call append via existing /admin/manage POST form endpoint simpler: use fetch to /admin/manage
    const form = new FormData();
    form.append('code', code);
    form.append('step', step);
    const res = await fetch('/admin/manage', {method:'POST', body: form});
    const txt = await res.text();
    alert('تم إضافة المرحلة');
    closeModal();
    loadClientDetails(code);
  } else {
    const name = document.getElementById('newName').value.trim();
    const service = document.getElementById('newService').value.trim();
    if(!name){ alert('اكتب اسم العميل'); return; }
    const res = await fetch('/admin/api/add-client', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name, service})
    });
    const data = await res.json();
    if(data.ok){ alert('تم إضافة العميل. الكود: ' + data.code); closeModal(); loadClients(); }
    else alert('خطأ: ' + (data.error||''));
  }
}

// on load
document.addEventListener('DOMContentLoaded', ()=> {
  loadClients();
});
