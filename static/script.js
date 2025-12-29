function track() {
    const code = document.getElementById("code").value.trim().toUpperCase();
    const result = document.getElementById("result");

    if (!code) {
        alert("من فضلك أدخل كود المتابعة");
        return;
    }

    result.innerHTML = "جاري البحث...";

    fetch(`/track?code=${code}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                result.innerHTML = `<strong>${data.error}</strong>`;
                return;
            }

            let checklistHtml = "";
            if(data.checklist && data.checklist.length){
                checklistHtml = '<ul>';
                data.checklist.forEach(item => {
                    checklistHtml += `<li>${item.done ? '✅' : '⏳'} ${item.name}</li>`;
                });
                checklistHtml += '</ul>';
            }

            result.innerHTML = `
                <h3>تفاصيل الطلب</h3>
                <p><strong>الاسم:</strong> ${data.name}</p>
                <p><strong>الخدمة:</strong> ${data.service}</p>
                ${checklistHtml}
            `;
        })
        .catch(() => { result.innerHTML = "حدث خطأ في الاتصال"; });
}
