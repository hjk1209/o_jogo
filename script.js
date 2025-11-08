document.addEventListener('DOMContentLoaded', () => {

    const form = document.getElementById('registro-form');
    const messageDiv = document.getElementById('aropiak-message');
    const formContainer = document.querySelector('.terminal-form');

    form.addEventListener('submit', async (event) => {
        
        event.preventDefault(); 

        const formData = {
            nomeAventureiro: document.getElementById('nome-aventureiro').value,
            nomeJogador: document.getElementById('nome-jogador').value,
            classeOrigem: document.getElementById('classe-origem').value,
            motivacao: document.getElementById('motivacao').value,
        };

        // Salva o nome do aventureiro no "Armazenamento Local" do navegador
        // para que a próxima página possa lê-lo.
        localStorage.setItem('aventureiroNome', formData.nomeAventureiro);

        try {
            const response = await fetch('http://127.0.0.1:5000/registrar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData), 
            });

            if (!response.ok) {
                throw new Error(`Falha no registro! Status: ${response.status}`);
            }

            // --- ESTA É A MUDANÇA PRINCIPAL ---
            // Se o envio para o backend foi um SUCESSO, 
            // redireciona o usuário para a página do "aplicativo".
            window.location.href = "kaibora.html";

        } catch (error) {
            // Se der erro (ex: backend desligado), mostra na tela
            console.error("Erro ao enviar dados:", error);
            messageDiv.innerHTML = `"Oh não! Aventureiro, parece que... *zzzt*... minha conexão com a Guilda caiu! Não consigo processar seu registro. <br><br> (Erro: ${error.message})"`;
            messageDiv.style.color = "red";
            messageDiv.style.borderColor = "red";
        }
    });
});