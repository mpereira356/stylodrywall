from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash
from ..forms import LoginForm
from ..models import User
from ..extensions import limiter

bp=Blueprint("auth",__name__,url_prefix="/auth")
@bp.route("/login",methods=["GET","POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated: return redirect(url_for("admin.dashboard"))
    form=LoginForm()
    if form.validate_on_submit():
        user=User.query.filter_by(email=form.username.data.lower().strip(),active=True).first()
        if user and check_password_hash(user.password_hash,form.password.data):
            session.clear(); login_user(user); return redirect(url_for("admin.dashboard"))
        flash("Usuário ou senha inválidos.","danger")
    return render_template("auth/login.html",form=form)
@bp.post("/logout")
def logout(): logout_user(); session.clear(); return redirect(url_for("public.home"))
