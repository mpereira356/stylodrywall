import os
import click
from flask import Flask
from werkzeug.security import generate_password_hash
from .config import Config
from .extensions import db, migrate, login_manager, csrf, limiter

def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app); migrate.init_app(app, db); login_manager.init_app(app)
    csrf.init_app(app); limiter.init_app(app)
    login_manager.login_view = "auth.login"; login_manager.login_message = "Entre para acessar o painel."
    from .models import User
    @login_manager.user_loader
    def load_user(user_id): return db.session.get(User, int(user_id))
    from .public.routes import bp as public_bp
    from .auth.routes import bp as auth_bp
    from .admin.routes import bp as admin_bp
    app.register_blueprint(public_bp); app.register_blueprint(auth_bp); app.register_blueprint(admin_bp)
    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net"
        return response
    register_cli(app)
    return app

def register_cli(app):
    from .models import User, Role, Unit, Category
    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        units = ["UN","PC","CX","PCT","KG","G","M","CM","M²","M³","L","ML","ROLO","BARRA","SACO","BALDE"]
        cats = ["Placas","Perfis","Canaletas","Tabicas","Gesso","Massas","Parafusos","Fitas","Acessórios","Ferramentas","Outros"]
        for code in units:
            if not Unit.query.filter_by(code=code).first(): db.session.add(Unit(code=code, name=code))
        for name in cats:
            if not Category.query.filter_by(name=name).first(): db.session.add(Category(name=name))
        if not Role.query.filter_by(name="ADMINISTRADOR").first(): db.session.add(Role(name="ADMINISTRADOR"))
        db.session.commit(); click.echo("Banco e cadastros iniciais criados.")
    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt="Nome")
    @click.password_option(confirmation_prompt=True)
    def create_admin(email, name, password):
        if len(password) < 10: raise click.ClickException("A senha precisa ter ao menos 10 caracteres.")
        role = Role.query.filter_by(name="ADMINISTRADOR").first()
        if not role: raise click.ClickException("Execute flask init-db primeiro.")
        user = User(name=name, email=email.lower().strip(), role=role, password_hash=generate_password_hash(password))
        db.session.add(user); db.session.commit(); click.echo("Administrador criado com segurança.")
