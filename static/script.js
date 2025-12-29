function track(){
    const code=document.getElementById("code").value.trim().toUpperCase();
    const result=document.getElementById("result");
    if(!code){alert("من فضلك أدخل كود المتابعة"); return;}
    result.innerHTML="جاري البحث...";
    fetch(`/track?code=${code}`)
        .then(res=>res.json())
        .then(data=>{
            if(data.error){result.innerHTML=`<strong>${data.error}</strong>`;return;}
            let checklistHTML = '';
            data.checklist.forEach(step=>{
                checklistHTML += `<li>${step.done ? '✅' : '❌'} ${step.name}</li>`;
            });
            result.innerHTML=`
                <div class="card">
                    <p><strong>الاسم:</strong> ${data.name}</p>
                    <p><strong>الخدمة:</strong> ${data.service}</p>
                    <h4>المراحل:</h4>
                    <ul>${checklistHTML}</ul>
                </div>
            `;
        })
        .catch(()=>{result.innerHTML="حدث خطأ في الاتصال بالخادم";});
}
