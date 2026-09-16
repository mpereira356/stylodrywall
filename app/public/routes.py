from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from ..extensions import db
from ..forms import ContactForm
from ..models import Service, ContactRequest

bp=Blueprint("public",__name__)
DEFAULT_SERVICES=[("Forros de Gesso e Drywall","Soluções precisas para ambientes modernos e bem acabados.","bi-layers"),("Divisórias Drywall","Rapidez, isolamento e flexibilidade para transformar espaços.","bi-grid-1x2"),("Tabicas e Sancas","Detalhes arquitetônicos que valorizam iluminação e acabamento.","bi-stars"),("Tratamento Acústico","Conforto sonoro para residências, escritórios e comércios.","bi-volume-mute"),("Nichos e Iluminação","Elementos sob medida integrados ao seu projeto.","bi-lightbulb"),("Reformas e Acabamento","Execução completa com organização, cuidado e prazo.","bi-house-check")]
@bp.route("/")
def home():
    services=Service.query.filter_by(active=True).order_by(Service.position).all()
    return render_template("public/home.html",services=services or DEFAULT_SERVICES,whatsapp=current_app.config["WHATSAPP_NUMBER"])
@bp.route("/orcamento",methods=["GET","POST"])
def quote_request():
    form=ContactForm()
    if form.validate_on_submit():
        request=ContactRequest(**{field:getattr(form,field).data for field in ["name","phone","whatsapp","email","service_type","description","location","notes"]})
        db.session.add(request); db.session.commit(); flash("Solicitação recebida! Nossa equipe entrará em contato.","success"); return redirect(url_for("public.home")+"#contato")
    return render_template("public/contact.html",form=form)
