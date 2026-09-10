# Stylo Drywall

Site institucional e base de ERP em Flask, com identidade preto/dourado, autenticação privada, dashboard, estoque decimal auditável, financeiro, obras, clientes, fornecedores e solicitações de orçamento.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
flask --app run.py init-db
flask --app run.py create-admin
flask --app run.py run
```

Acesse `http://127.0.0.1:5000` e o painel em `/admin`.

Em produção, defina uma `SECRET_KEY` forte, use PostgreSQL em `DATABASE_URL`, ative `SESSION_COOKIE_SECURE=true`, configure HTTPS e um backend persistente para o rate limiter.

## Arquitetura

- `app/public`: site e captura de orçamento
- `app/auth`: login protegido e rate limit
- `app/admin`: dashboard e módulos internos
- `app/services.py`: regras transacionais de estoque e auditoria
- `app/models.py`: modelos SQLAlchemy com `Numeric` para dinheiro e quantidades
- `tests`: regras críticas automatizadas

Toda mudança de quantidade passa por `move_stock`, que valida saldo, calcula custo e cria histórico. Usuários administrativos são criados apenas pelo comando interativo `create-admin`; nenhuma senha padrão fica no código.

## Testes

```powershell
pytest -q
```
