# Instalação — FortiAnalyzer Reports

## Versão compilada (.exe) — time de projetos

1. Receba a pasta **`FortiAnalyzer-Reports`** (gerada em `dist\` pelo build).
2. Copie a pasta para o computador (ex.: `C:\Apps\FortiAnalyzer-Reports\`).
3. Duplo clique em **`FortiAnalyzer-Reports.exe`**.
4. O portal abre em **http://localhost:8000/login.html**.
5. Informe usuário e senha do FortiAnalyzer no login.

**Não precisa** de Python, `.venv` nem `install.bat`.

Na primeira execução, o `.env` é criado automaticamente ao lado do `.exe`.

## Versão por código-fonte (desenvolvimento)

1. Duplo clique em **`install.bat`**.
2. O assistente abre em **http://127.0.0.1:8765**.
3. Clique em **Instalar** e aguarde.
4. Uso diário: **`FortiAnalyzer Reports.bat`**.

## Compilar o .exe (desenvolvimento)

```powershell
powershell -ExecutionPolicy Bypass -File install\build_app.ps1
```

Saída: `dist\FortiAnalyzer-Reports\` — distribua **esta pasta inteira** ao time.

## Desinstalar

- **Versão .exe:** apague a pasta `FortiAnalyzer-Reports` e o atalho na área de trabalho.
- **Versão código-fonte:** execute `Desinstalar.bat` ou apague `.venv`, `output` e a pasta do projeto.
