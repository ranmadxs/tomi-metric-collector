function copyCode(elementId, button) {
    const code = document.getElementById(elementId).textContent;
    navigator.clipboard.writeText(code).then(() => {
        button.innerHTML = '✓ Copiado';
        button.classList.add('copied');
        setTimeout(() => {
            button.innerHTML = '📋 Copiar';
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Error al copiar:', err);
        button.innerHTML = '❌ Error';
        setTimeout(() => {
            button.innerHTML = '📋 Copiar';
        }, 2000);
    });
}
