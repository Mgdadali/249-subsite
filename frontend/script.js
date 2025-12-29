function track() {
    const code = document.getElementById("codeInput").value.trim().toUpperCase();
    const result = document.getElementById("result");

    if (!code) {
        alert("من فضلك أدخل كود المتابعة");
        return;
    }

    result.classList.remove("hidden");
    result.innerHTML = "جاري البحث...";

    fetch(`https://two49-subsite.onrender.com/track?code=${code}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                result.innerHTML = `<strong>${data.error}</strong>`;
                return;
            }

            result.innerHTML = `
                <h3>تفاصيل الطلب</h3>
                <p><strong>الاسم:</strong> ${data.name}</p>
                <p><strong>الخدمة:</strong> ${data.service}</p>
                <p><strong>الحالة:</strong> ${data.status}</p>
                <p><strong>المرحلة الحالية:</strong> ${data.step}</p>

                <div class="progress">
                    <div class="progress-bar" style="width:${getProgress(data.status)}%"></div>
                </div>

                <p><strong>ملاحظات:</strong> ${data.notes}</p>
                <p class="date"><strong>آخر تحديث:</strong> ${data.last_update}</p>
            `;
        })
        .catch(() => {
            result.innerHTML = "حدث خطأ في الاتصال بالخادم";
        });
}

function getProgress(status) {
    const map = {
        "مستلم": 20,
        "قيد الإجراء": 40,
        "تم التقديم": 60,
        "بانتظار الرد": 80,
        "مكتمل": 100
    };
    return map[status] || 30;
}
