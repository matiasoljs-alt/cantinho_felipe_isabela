# Nosso cantinho — Felipe & Isabella 💗

Site responsivo com FastAPI, SQLite, contador desde 23/06/2026, mensagens fofas, linha do tempo e álbum administrável.

## Rodar no Linux Mint
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Edite `.env`: escolha uma senha forte e uma chave aleatória longa para `SESSION_SECRET`. Depois:
```bash
uvicorn app.main:app --reload
```
Abra `http://127.0.0.1:8000`; painel: `http://127.0.0.1:8000/admin`.

## Publicação
Este projeto grava fotos e SQLite em disco local. Em Vercel/serverless, arquivos locais não são persistentes; podem sumir após novo deploy. Para manter esta arquitetura, use hospedagem com disco persistente (por exemplo, Render com Persistent Disk montado em `/var/data`) e configure `DATABASE_PATH=/var/data/casal.db`, `UPLOAD_DIR=/var/data/uploads`. Confira custos e disponibilidade do disco no provedor.

Para um deploy gratuito/serverless, será necessário trocar o armazenamento local por banco e armazenamento externos (por exemplo, Supabase). O painel `/admin` é protegido, mas as páginas `/` e `/album` são públicas nesta versão inicial. Se quiser que só vocês dois vejam o álbum, é preciso exigir login também nessas páginas.

**Segurança:** não publique `.env` no GitHub. Troque a senha antes de publicar. Configure `COOKIE_SECURE=true` somente quando o site estiver usando HTTPS. `felipe67@` foi mantido como identificador de login, embora não seja um endereço de e-mail completo.
