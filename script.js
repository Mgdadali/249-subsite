function track() {
    const code = document.getElementById("codeInput").value.trim();
    const result = document.getElementById("result");

    if (!code) {
        alert("من فضلك أدخل كود المتابعة");
        return;
    }

    fetch(`https://YOUR-BACKEND-URL/track?code=${code}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                result.classList.remove("hidden");
                result.innerHTML = `<strong>${data.error}</strong>`;
                return;
            }

            result.classList.remove("hidden");
            result.innerHTML = `
                <p><strong>الاسم:</strong> ${data.name}</p>
                <p><strong>الخدمة:</strong> ${data.service}</p>
                <p><strong>الحالة:</strong> ${data.status}</p>
                <p><strong>المرحلة الحالية:</strong> ${data.step}</p>
                <p><strong>ملاحظات:</strong> ${data.notes}</p>
                <p><strong>آخر تحديث:</strong> ${data.last_update}</p>
            `;
        })
        .catch(() => {
            result.classList.remove("hidden");
            result.innerHTML = "حدث خطأ في الاتصال بالخادم";
        });
}
