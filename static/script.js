// عام: تستخدمه الصفحة الرئيسية والصفحة الخاصة بالعميل
// دوال: renderClientChecklist(code) و trackHome() متاحة

// توجيه من الصفحة الرئيسية للصفحة المخصصة
function trackHome() {
  const input = document.getElementById('codeInput');
  if(!input) return;
  const code = input.value.trim().toUpperCase();
  if(!code){ alert('من فضلك أدخل كود المتابعة'); return; }
  window.location.href = `/client/${encodeURIComponent(code)}`;
}

// الدالة الأساسية لعرض صفحة العميل (CheckList)
async function renderClientChecklist(code){
  const nameEl = document.getElementById('clientName');
  const serviceEl = document.getElementById('clientService');
  const listEl = document.getElementById('checklistList');
  const pctEl = document.getElementById('progressPct');
  const barEl = document.getElementById('progressBar');
  const textEl = document.getElementById('progressText');
  const notesEl = document.getElementById('notes');

  nameEl.textContent = 'جاري التحميل...';
  serviceEl.textContent = '';
  listEl.innerHTML = '';
  notesEl.textContent = '';

  try {
    const res = await fetch(`/track?code=${encodeURIComponent(code)}`);
    const data = await res.json();
    if(data.error){
      nameEl.textContent = data.error;
      return;
    }

    // عرض معلومات العميل
    nameEl.textContent = data.name || 'عميل';
    serviceEl.textContent = data.service ? `الخدمة: ${data.service}` : '';

    // بناء القائمة
    const steps = data.checklist || [];
    let completed = 0;
    steps.forEach((s, idx) => {
      const li = document.createElement('li');
      li.className = s.done ? 'done' : '';
      li.innerHTML = `
        <div class="step-left">
          <div class="step-badge">${idx+1}</div>
          <div class="step-text"><strong>${s.name}</strong><div class="muted"></div></div>
        </div>
        <div class="step-right">${s.done ? '✅' : '⏳'}</div>
      `;
      listEl.appendChild(li);
      if (s.done) completed++;
    });

    // نسبة التقدم
    const percent = steps.length ? Math.round((completed / steps.length) * 100) : 0;
    pctEl.textContent = percent + "%";
    barEl.style.width = percent + "%";
    // لون الشريط أخضر لو 100% وإلا أزرق
    if (percent === 100) barEl.style.background = 'linear-gradient(90deg,#28a745,#1db954)';
    else barEl.style.background = 'linear-gradient(90deg,var(--blue-900,var(--blue-600)),var(--blue-600))';

    textEl.textContent = `تم إتمام ${completed} من ${steps.length} مرحلة (${percent}%)`;

    // ملاحظة: إذا واجهت بيانات إضافية مثل last_update أو notes من API اعرضها
    if (data.last_update) notesEl.textContent = `آخر تحديث: ${data.last_update}`;
    if (data.notes) {
      notesEl.textContent += (notesEl.textContent ? ' — ' : '') + `ملاحظة: ${data.notes}`;
    }

  } catch (err) {
    nameEl.textContent = 'حدث خطأ في الاتصال بالخادم';
    console.error(err);
  }
}

// تصدير دالة لتُستخدم في checklist template
window.renderClientChecklist = renderClientChecklist;
window.trackHome = trackHome;
