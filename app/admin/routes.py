from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timezone
import calendar
import math
import re
import unicodedata
from math import ceil
from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Product, StockMovement, FinancialEntry, Project, ContactRequest, Customer, Supplier, Unit, Category, Purchase, PurchaseItem, ProjectMaterial, Sale, SaleItem
from ..forms import MovementForm
from ..services import move_stock, audit

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.before_request
@login_required
def protect():
    pass

@bp.route("/")
def dashboard():
    products = Product.query.filter_by(active=True).all()
    entries = FinancialEntry.query.all()
    receivable = sum((e.balance for e in entries if e.kind == "RECEITA"), Decimal(0))
    payable = sum((e.balance for e in entries if e.kind == "DESPESA"), Decimal(0))
    today = date.today()
    month_entries = [e for e in entries if e.created_at and e.created_at.year == today.year and e.created_at.month == today.month]
    month_revenue = sum((Decimal(e.paid_amount or 0) for e in month_entries if e.kind == "RECEITA"), Decimal(0))
    month_expenses = sum((Decimal(e.paid_amount or 0) for e in month_entries if e.kind == "DESPESA"), Decimal(0))
    metrics = {"stock_value": sum((Decimal(p.current_quantity) * Decimal(p.average_cost) for p in products), Decimal(0)), "items": len(products), "products": len(products), "low": sum(p.low_stock for p in products), "receivable": receivable, "payable": payable, "balance": month_revenue - month_expenses, "revenue": month_revenue, "expenses": month_expenses, "profit": month_revenue - month_expenses, "projects": Project.query.filter(Project.status == "Em andamento").count(), "quotes": ContactRequest.query.filter_by(status="Novo").count()}
    months = []
    for offset in range(5, -1, -1):
        absolute = today.year * 12 + today.month - 1 - offset
        year, month_index = divmod(absolute, 12)
        months.append((year, month_index + 1))
    labels = [f"{calendar.month_abbr[m]}/{str(y)[2:]}" for y, m in months]
    revenue_data, expense_data, stock_in_data, stock_out_data = [], [], [], []
    movements_all = StockMovement.query.all()
    for year, month in months:
        monthly_finance = [e for e in entries if e.created_at and e.created_at.year == year and e.created_at.month == month]
        revenue_data.append(float(sum((Decimal(e.paid_amount or 0) for e in monthly_finance if e.kind == "RECEITA"), Decimal(0))))
        expense_data.append(float(sum((Decimal(e.paid_amount or 0) for e in monthly_finance if e.kind == "DESPESA"), Decimal(0))))
        monthly_stock = [m for m in movements_all if m.created_at and m.created_at.year == year and m.created_at.month == month]
        stock_in_data.append(sum(1 for m in monthly_stock if m.movement_type in {"Entrada", "Devolução", "Ajuste positivo"}))
        stock_out_data.append(sum(1 for m in monthly_stock if m.movement_type in {"Saída", "Perda", "Ajuste negativo", "Uso em obra"}))
    recent = StockMovement.query.order_by(StockMovement.created_at.desc()).limit(7).all()
    lows = [p for p in products if p.low_stock]
    chart_data = {"labels": labels, "revenue": revenue_data, "expenses": expense_data, "stock_in": stock_in_data, "stock_out": stock_out_data}
    return render_template("admin/dashboard.html", metrics=metrics, recent=recent, movements=recent, low_products=lows, low_stock=lows, chart_data=chart_data)

@bp.route("/estoque")
def inventory():
    search = request.args.get("q", "").strip()
    query = Product.query
    if search:
        term = f"%{search}%"
        query = query.filter(db.or_(Product.name.ilike(term), Product.internal_code.ilike(term)))
    return render_template("admin/inventory.html", products=query.order_by(Product.name).all(), q=search)

@bp.route("/estoque/baixo")
def low_stock():
    products = [p for p in Product.query.filter_by(active=True).all() if p.low_stock]
    return render_template("admin/inventory.html", products=products, q="")

@bp.route("/estoque/produto/<string:internal_code>/editar", methods=["GET", "POST"])
def edit_product(internal_code):
    product = Product.query.filter_by(internal_code=internal_code).first_or_404()
    if request.method == "POST":
        try:
            name = " ".join(request.form.get("name", "").split())
            if not name: raise ValueError("Informe o nome do produto.")
            if product_name_exists(name, exclude_id=product.id):
                raise ValueError("Já existe outro produto cadastrado com esse nome.")
            category = db.get_or_404(Category, int(request.form["category_id"]))
            unit = db.get_or_404(Unit, int(request.form["unit_id"]))
            supplier_id = request.form.get("supplier_id")
            length = decimal_field("piece_length") or None
            width = decimal_field("piece_width") or None
            old = {"nome": product.name, "codigo": product.internal_code}
            product.name = name
            product.internal_code = generate_product_code(name, category, length, width)
            product.description = request.form.get("description")
            product.category = category
            product.unit = unit
            product.supplier = db.session.get(Supplier, int(supplier_id)) if supplier_id else None
            product.sku = request.form.get("sku") or None
            product.barcode = request.form.get("barcode") or None
            product.minimum_stock = decimal_field("minimum_stock")
            product.maximum_stock = decimal_field("maximum_stock") or None
            product.piece_length = length
            product.piece_width = width
            product.piece_height = decimal_field("piece_height") or None
            product.coverage_area = length * width if length and width else None
            product.estimated_price = decimal_field("sale_price") or None
            product.location = request.form.get("location") or None
            product.notes = request.form.get("notes") or None
            product.active = request.form.get("active") == "1"
            audit("Produto editado", "estoque", product.id, current_user, old=old,
                  new={"nome": product.name, "codigo": product.internal_code}, ip=request.remote_addr)
            db.session.commit()
            flash(f"Produto atualizado. O código foi ajustado automaticamente para {product.internal_code}.", "success")
            return redirect(url_for("admin.inventory"))
        except (ValueError, KeyError) as error:
            db.session.rollback(); flash(str(error), "danger")
    return render_template("admin/product_edit.html", product=product,
                           units=Unit.query.filter_by(active=True).all(),
                           categories=Category.query.order_by(Category.name).all(),
                           suppliers=Supplier.query.filter_by(active=True).order_by(Supplier.company_name).all())

@bp.post("/estoque/produto/<string:internal_code>/remover")
def delete_product(internal_code):
    product = Product.query.filter_by(internal_code=internal_code).first_or_404()
    old = {"nome": product.name, "codigo": product.internal_code}
    product_id = product.id
    for item in PurchaseItem.query.filter_by(product_id=product.id).all():
        purchase = item.purchase
        entry = purchase_financial_entry(purchase.id)
        if len(purchase.items) == 1:
            if entry: db.session.delete(entry)
            db.session.delete(purchase)
        else:
            purchase.total = Decimal(purchase.total or 0) - Decimal(item.total or 0)
            if entry: entry.amount = entry.paid_amount = purchase.total
            db.session.delete(item)
    for item in SaleItem.query.filter_by(product_id=product.id).all():
        sale = item.sale
        entry = FinancialEntry.query.filter(
            FinancialEntry.kind == "RECEITA",
            FinancialEntry.description.like(f"Venda #{sale.id} -%"),
        ).order_by(FinancialEntry.id.desc()).first()
        if len(sale.items) == 1:
            if entry: db.session.delete(entry)
            db.session.delete(sale)
        else:
            sale.total = Decimal(sale.total or 0) - Decimal(item.total or 0)
            if entry:
                entry.amount = sale.total
                entry.paid_amount = sale.total if sale.status == "Pago" else 0
            db.session.delete(item)
    ProjectMaterial.query.filter_by(product_id=product.id).delete(synchronize_session=False)
    StockMovement.query.filter_by(product_id=product.id).delete(synchronize_session=False)
    db.session.delete(product)
    audit("Produto excluído", "estoque", product_id, current_user, old=old, ip=request.remote_addr)
    db.session.commit()
    flash("Produto e todos os registros relacionados foram excluídos definitivamente.", "success")
    return redirect(url_for("admin.inventory"))

@bp.route("/movimentacoes", methods=["GET", "POST"])
def movements():
    form = MovementForm()
    form.product_id.choices = [(p.id, f"{p.internal_code} - {p.name} ({p.current_quantity} {p.unit.code})") for p in Product.query.filter_by(active=True).order_by(Product.name)]
    if form.validate_on_submit():
        product = db.session.get(Product, form.product_id.data)
        try:
            movement = move_stock(product, form.movement_type.data, form.quantity.data, current_user, form.unit_cost.data, notes=form.notes.data)
            audit("Movimentação de estoque", "estoque", movement.id, current_user, new={"tipo": movement.movement_type, "quantidade": str(movement.quantity)}, ip=request.remote_addr)
            db.session.commit()
            flash("Movimentação registrada com histórico.", "success")
            return redirect(url_for("admin.movements"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
    rows = StockMovement.query.order_by(StockMovement.created_at.desc()).limit(100).all()
    return render_template("admin/movements.html", form=form, rows=rows, movements=rows)

@bp.route("/orcamento")
@bp.route("/orcamentos")
def quote_requests():
    status = request.args.get("status", "").strip()
    search = request.args.get("q", "").strip()
    query = ContactRequest.query
    if status:
        query = query.filter(ContactRequest.status == status)
    if search:
        term = f"%{search}%"
        query = query.filter(db.or_(ContactRequest.name.ilike(term), ContactRequest.phone.ilike(term), ContactRequest.email.ilike(term)))
    items = query.order_by(ContactRequest.created_at.desc()).all()
    totals = {"all": ContactRequest.query.count(), "new": ContactRequest.query.filter_by(status="Novo").count(), "contacted": ContactRequest.query.filter_by(status="Em contato").count(), "closed": ContactRequest.query.filter_by(status="Concluído").count()}
    return render_template("admin/quotes.html", requests_list=items, totals=totals, current_status=status, search=search)

@bp.route("/orcamentos/<int:request_id>")
def quote_request_detail(request_id):
    quote = db.get_or_404(ContactRequest, request_id)
    return render_template("admin/quote_detail.html", quote=quote)

@bp.post("/orcamentos/<int:request_id>/status")
def quote_request_status(request_id):
    quote = db.get_or_404(ContactRequest, request_id)
    new_status = request.form.get("status", "")
    if new_status not in {"Novo", "Em contato", "Concluído", "Cancelado"}:
        flash("Status inválido.", "danger")
    else:
        previous = quote.status
        quote.status = new_status
        audit("Status do orçamento alterado", "orcamentos", quote.id, current_user, old={"status": previous}, new={"status": new_status}, ip=request.remote_addr)
        db.session.commit()
        flash("Status atualizado com sucesso.", "success")
    return redirect(url_for("admin.quote_request_detail", request_id=request_id))

def decimal_field(name, default="0"):
    field_labels = {
        "quantity": "Quantidade",
        "unit_cost": "Custo por unidade",
        "sale_price": "Preço de venda",
        "minimum_stock": "Estoque mínimo",
        "maximum_stock": "Estoque máximo",
        "piece_length": "Comprimento da peça",
        "piece_width": "Largura da peça",
        "piece_height": "Espessura da peça",
        "unit_price": "Preço por unidade",
    }
    value = request.form.get(name)
    if value is None or not value.strip():
        value = default
    try:
        text = str(value).strip().replace(" ", "")
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", text):
            text = text.replace(".", "")
        return Decimal(text)
    except (InvalidOperation, AttributeError):
        label = field_labels.get(name, name)
        raise ValueError(f"Confira o campo “{label}”. Digite somente números, por exemplo: 10,50.")

def generate_product_code(name, category, length=None, width=None):
    def clean(value):
        normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
        return re.sub(r"[^A-Z0-9]", "", normalized.upper())
    category_code = clean(category.name)[:3] or "MAT"
    name_words = [clean(word) for word in name.split() if clean(word)]
    name_code = "".join(word[:3] for word in name_words[:2])[:6] or "ITEM"
    dimension = ""
    if length:
        length_cm = int(Decimal(length) * 100)
        dimension = f"-{length_cm}"
        if width:
            width_cm = int(Decimal(width) * 100)
            dimension += f"X{width_cm}"
    prefix = f"{category_code}-{name_code}{dimension}"
    existing = Product.query.filter(Product.internal_code.like(f"{prefix}-%")).count()
    sequence = existing + 1
    code = f"{prefix}-{sequence:03d}"
    while Product.query.filter_by(internal_code=code).first():
        sequence += 1; code = f"{prefix}-{sequence:03d}"
    return code

def product_name_exists(name, exclude_id=None):
    normalized = " ".join(name.split()).casefold()
    query = db.session.query(Product.id, Product.name)
    if exclude_id is not None: query = query.filter(Product.id != exclude_id)
    return any(" ".join(product_name.split()).casefold() == normalized
               for _, product_name in query.all())

@bp.route("/fornecedores", methods=["GET", "POST"])
def suppliers():
    if request.method == "POST":
        name = request.form.get("company_name", "").strip()
        if not name:
            flash("Informe o nome do fornecedor.", "danger")
        else:
            supplier = Supplier(company_name=name, document=request.form.get("document"), phone=request.form.get("phone"), email=request.form.get("email"), address=request.form.get("address"), specialty=request.form.get("specialty"), notes=request.form.get("notes"))
            db.session.add(supplier); db.session.commit(); flash("Fornecedor cadastrado.", "success")
            return redirect(url_for("admin.suppliers"))
    return render_template("admin/suppliers.html", suppliers=Supplier.query.order_by(Supplier.company_name).all())

@bp.route("/clientes", methods=["GET", "POST"])
def customers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Informe o nome do cliente.", "danger")
        else:
            customer = Customer(name=name, document=request.form.get("document"), phone=request.form.get("phone"), whatsapp=request.form.get("whatsapp"), email=request.form.get("email"), address=request.form.get("address"), notes=request.form.get("notes"))
            db.session.add(customer); db.session.commit(); flash("Cliente cadastrado.", "success")
            return redirect(url_for("admin.customers"))
    return render_template("admin/customers.html", customers=Customer.query.order_by(Customer.name).all())

@bp.route("/compras", methods=["GET", "POST"])
def purchases():
    if request.method == "POST":
        try:
            supplier_id = request.form.get("supplier_id")
            supplier = db.session.get(Supplier, int(supplier_id)) if supplier_id else None
            quantity = decimal_field("quantity")
            cost = decimal_field("unit_cost")
            sale_price = decimal_field("sale_price")
            if quantity <= 0 or cost < 0:
                raise ValueError("Quantidade e custo precisam ser válidos.")
            product_id = request.form.get("product_id")
            if product_id:
                product = db.get_or_404(Product, int(product_id))
                if sale_price > 0: product.estimated_price = sale_price
            else:
                unit = db.get_or_404(Unit, int(request.form["unit_id"]))
                category = db.get_or_404(Category, int(request.form["category_id"]))
                name = " ".join(request.form.get("product_name", "").split())
                if not name: raise ValueError("Informe o nome do novo produto.")
                if product_name_exists(name):
                    raise ValueError("Já existe um produto cadastrado com esse nome. Selecione-o na lista de produtos já cadastrados.")
                length = decimal_field("piece_length") or None
                width = decimal_field("piece_width") or None
                code = generate_product_code(name, category, length, width)
                product = Product(internal_code=code, name=name, unit=unit, category=category, supplier=supplier, minimum_stock=decimal_field("minimum_stock"), estimated_price=sale_price, current_quantity=0, piece_length=length, piece_width=width, piece_height=decimal_field("piece_height") or None, coverage_area=(length*width if length and width else None))
                db.session.add(product); db.session.flush()
            purchase = Purchase(supplier=supplier, purchase_date=date.fromisoformat(request.form.get("purchase_date") or date.today().isoformat()), document=request.form.get("document"), notes=request.form.get("notes"), total=quantity*cost, user=current_user)
            item = PurchaseItem(purchase=purchase, product=product, quantity=quantity, unit_cost=cost, total=quantity*cost)
            db.session.add_all([purchase, item]); db.session.flush()
            move_stock(product, "Entrada", quantity, current_user, cost, supplier=supplier, notes=f"Compra #{purchase.id}", document=purchase.document)
            supplier_name = supplier.company_name if supplier else "Compra sem fornecedor"
            db.session.add(FinancialEntry(kind="DESPESA", description=f"Compra #{purchase.id} - {supplier_name}", category="Compra de material", amount=purchase.total, paid_amount=purchase.total, paid_at=purchase.purchase_date, due_date=purchase.purchase_date, status="Pago", supplier_id=supplier.id if supplier else None))
            audit("Compra registrada", "compras", purchase.id, current_user, new={"produto": product.name, "quantidade": str(quantity), "total": str(purchase.total)}, ip=request.remote_addr)
            db.session.commit(); flash("Compra registrada e estoque atualizado.", "success")
            return redirect(url_for("admin.purchases"))
        except (ValueError, KeyError) as error:
            db.session.rollback(); flash(str(error), "danger")
    return render_template("admin/purchases.html", purchases=Purchase.query.order_by(Purchase.created_at.desc()).all(), suppliers=Supplier.query.filter_by(active=True).all(), products=Product.query.filter_by(active=True).all(), units=Unit.query.filter_by(active=True).all(), categories=Category.query.order_by(Category.name).all(), today=date.today().isoformat())

def purchase_financial_entry(purchase_id):
    return FinancialEntry.query.filter(
        FinancialEntry.kind == "DESPESA",
        FinancialEntry.description.like(f"Compra #{purchase_id} -%"),
    ).order_by(FinancialEntry.id.desc()).first()

@bp.route("/compras/<int:purchase_id>/editar", methods=["GET", "POST"])
def edit_purchase(purchase_id):
    purchase = db.get_or_404(Purchase, purchase_id)
    if not purchase.items:
        flash("Esta compra não possui um item para editar.", "danger")
        return redirect(url_for("admin.purchases"))
    item = purchase.items[0]
    if request.method == "POST":
        try:
            quantity = decimal_field("quantity")
            cost = decimal_field("unit_cost")
            if quantity <= 0 or cost < 0:
                raise ValueError("A quantidade deve ser maior que zero e o custo não pode ser negativo.")
            old_quantity, old_cost = Decimal(item.quantity), Decimal(item.unit_cost)
            difference = quantity - old_quantity
            if difference:
                movement_type = "Ajuste positivo" if difference > 0 else "Ajuste negativo"
                move_stock(item.product, movement_type, abs(difference), current_user, cost,
                           supplier=purchase.supplier, notes=f"Edição da compra #{purchase.id}",
                           document=request.form.get("document"))
            supplier_id = request.form.get("supplier_id")
            purchase.supplier = db.session.get(Supplier, int(supplier_id)) if supplier_id else None
            purchase.purchase_date = date.fromisoformat(request.form.get("purchase_date") or date.today().isoformat())
            purchase.document = request.form.get("document")
            purchase.notes = request.form.get("notes")
            purchase.total = quantity * cost
            item.quantity, item.unit_cost, item.total = quantity, cost, purchase.total
            item.product.last_cost = cost
            entry = purchase_financial_entry(purchase.id)
            supplier_name = purchase.supplier.company_name if purchase.supplier else "Compra sem fornecedor"
            if entry:
                entry.description = f"Compra #{purchase.id} - {supplier_name}"
                entry.amount = entry.paid_amount = purchase.total
                entry.paid_at = entry.due_date = purchase.purchase_date
                entry.supplier_id = purchase.supplier_id
            audit("Compra editada", "compras", purchase.id, current_user,
                  old={"quantidade": str(old_quantity), "custo": str(old_cost)},
                  new={"quantidade": str(quantity), "custo": str(cost)}, ip=request.remote_addr)
            db.session.commit()
            flash("Compra atualizada. O estoque e o financeiro também foram ajustados.", "success")
            return redirect(url_for("admin.purchases"))
        except (ValueError, KeyError) as error:
            db.session.rollback(); flash(str(error), "danger")
    return render_template("admin/purchase_edit.html", purchase=purchase, item=item,
                           suppliers=Supplier.query.filter_by(active=True).all())

@bp.post("/compras/<int:purchase_id>/remover")
def delete_purchase(purchase_id):
    purchase = db.get_or_404(Purchase, purchase_id)
    try:
        for item in purchase.items:
            current_stock = Decimal(item.product.current_quantity or 0)
            quantity = Decimal(item.quantity)
            if current_stock < quantity and not current_app.config["ALLOW_NEGATIVE_STOCK"]:
                raise ValueError("Estoque insuficiente")
            item.product.current_quantity = current_stock - quantity
        StockMovement.query.filter(db.or_(
            StockMovement.notes == f"Compra #{purchase.id}",
            StockMovement.notes == f"Edição da compra #{purchase.id}",
        )).delete(synchronize_session=False)
        entry = purchase_financial_entry(purchase.id)
        old = {"total": str(purchase.total), "itens": len(purchase.items)}
        if entry: db.session.delete(entry)
        db.session.delete(purchase)
        audit("Compra removida", "compras", purchase_id, current_user, old=old, ip=request.remote_addr)
        db.session.commit()
        flash("Compra removida. A quantidade foi retirada do estoque e a despesa foi removida do financeiro.", "success")
    except ValueError:
        db.session.rollback()
        flash("Não foi possível remover: parte desse material já saiu do estoque. Ajuste o estoque antes de remover a compra.", "danger")
    return redirect(url_for("admin.purchases"))

@bp.route("/vendas", methods=["GET", "POST"])
def sales():
    if request.method == "POST":
        try:
            product = db.get_or_404(Product, int(request.form["product_id"]))
            quantity = decimal_field("quantity")
            unit_price = decimal_field("unit_price")
            if quantity <= 0 or unit_price < 0:
                raise ValueError("Quantidade e preço precisam ser válidos.")
            customer_id = request.form.get("customer_id")
            sale = Sale(customer_id=int(customer_id) if customer_id else None, sale_date=date.fromisoformat(request.form.get("sale_date") or date.today().isoformat()), payment_method=request.form.get("payment_method"), status=request.form.get("status", "Pago"), total=quantity*unit_price, notes=request.form.get("notes"), user=current_user)
            line = SaleItem(sale=sale, product=product, quantity=quantity, unit_price=unit_price, unit_cost=product.average_cost or 0, total=quantity*unit_price)
            db.session.add_all([sale, line]); db.session.flush()
            move_stock(product, "Saída", quantity, current_user, product.average_cost, notes=f"Venda #{sale.id}")
            paid = sale.status == "Pago"
            db.session.add(FinancialEntry(kind="RECEITA", description=f"Venda #{sale.id} - {product.name}", category="Venda de material", amount=sale.total, paid_amount=sale.total if paid else 0, paid_at=sale.sale_date if paid else None, due_date=sale.sale_date, status=sale.status, payment_method=sale.payment_method, customer_id=sale.customer_id))
            audit("Venda registrada", "vendas", sale.id, current_user, new={"produto": product.name, "quantidade": str(quantity), "total": str(sale.total)}, ip=request.remote_addr)
            db.session.commit(); flash("Venda registrada e estoque atualizado.", "success")
            return redirect(url_for("admin.sales"))
        except (ValueError, KeyError) as error:
            db.session.rollback(); flash(str(error), "danger")
    return render_template("admin/sales.html", sales=Sale.query.order_by(Sale.created_at.desc()).all(), products=Product.query.filter_by(active=True).order_by(Product.name).all(), customers=Customer.query.order_by(Customer.name).all(), today=date.today().isoformat())

@bp.route("/obras", methods=["GET", "POST"])
def projects():
    if request.method == "POST":
        try:
            project = Project(name=request.form["name"].strip(), customer_id=int(request.form["customer_id"]), address=request.form.get("address"), start_date=date.fromisoformat(request.form.get("start_date") or date.today().isoformat()), expected_end=date.fromisoformat(request.form["expected_end"]) if request.form.get("expected_end") else None, status=request.form.get("status", "Em andamento"), sale_value=decimal_field("sale_value"), labor_cost=decimal_field("labor_cost"), other_cost=decimal_field("other_cost"))
            if not project.name: raise ValueError("Informe o nome da obra.")
            db.session.add(project); db.session.commit(); flash("Obra cadastrada.", "success")
            return redirect(url_for("admin.project_detail", project_id=project.id))
        except (ValueError, KeyError) as error:
            db.session.rollback(); flash(str(error), "danger")
    return render_template("admin/projects.html", projects=Project.query.order_by(Project.id.desc()).all(), customers=Customer.query.order_by(Customer.name).all(), today=date.today().isoformat())

@bp.route("/obras/<int:project_id>", methods=["GET", "POST"])
def project_detail(project_id):
    project = db.get_or_404(Project, project_id)
    if request.method == "POST":
        try:
            product = db.get_or_404(Product, int(request.form["product_id"]))
            quantity = decimal_field("quantity")
            movement = move_stock(product, "Uso em obra", quantity, current_user, product.average_cost, project=project, notes=f"Material usado na obra {project.name}")
            db.session.flush()
            material = ProjectMaterial(project=project, product=product, quantity=quantity, unit_cost=movement.unit_cost, total_cost=movement.total_cost)
            db.session.add(material); db.session.commit(); flash("Material lançado e retirado do estoque.", "success")
            return redirect(url_for("admin.project_detail", project_id=project.id))
        except (ValueError, KeyError) as error:
            db.session.rollback(); flash(str(error), "danger")
    return render_template("admin/project_detail.html", project=project, products=Product.query.filter_by(active=True).order_by(Product.name).all())

@bp.route("/calculadora", methods=["GET", "POST"])
def calculator():
    result = None
    values = {"length": "3", "width": "3", "plate_length": "1.80", "plate_width": "1.20", "bar_length": "3", "spacing": "0.40", "waste": "10"}
    if request.method == "POST":
        try:
            for key in values: values[key] = request.form.get(key, values[key])
            length=decimal_field("length"); width=decimal_field("width"); plate_length=decimal_field("plate_length"); plate_width=decimal_field("plate_width"); bar_length=decimal_field("bar_length"); spacing=decimal_field("spacing"); waste=decimal_field("waste")/Decimal(100)
            if min(length,width,plate_length,plate_width,bar_length,spacing) <= 0: raise ValueError("As medidas precisam ser maiores que zero.")
            area=length*width; perimeter=(length+width)*2; factor=Decimal(1)+waste; plate_area=plate_length*plate_width
            result={"area":area,"perimeter":perimeter,"plates":ceil(area*factor/plate_area),"plate_area":plate_area,"perimeter_m":perimeter*factor,"perimeter_bars":ceil(perimeter*factor/bar_length),"profiles_m":area/spacing*factor,"profile_bars":ceil((area/spacing*factor)/bar_length),"screws":ceil(area*Decimal(15)*factor),"tape_m":area*Decimal("1.5")*factor,"compound_kg":area*Decimal("0.5")*factor,"waste":waste*100}
        except ValueError as error: flash(str(error),"danger")
    return render_template("admin/calculator.html", result=result, values=values)

@bp.route("/financeiro", methods=["GET", "POST"])
def financial():
    if request.method == "POST":
        try:
            amount = decimal_field("amount")
            if amount <= 0: raise ValueError("Informe um valor maior que zero.")
            paid = request.form.get("status") == "Pago"
            entry = FinancialEntry(kind=request.form["kind"], description=request.form["description"].strip(), category=request.form.get("category"), amount=amount, paid_amount=amount if paid else 0, due_date=date.fromisoformat(request.form["due_date"]) if request.form.get("due_date") else None, paid_at=date.today() if paid else None, status=request.form.get("status", "Pendente"), payment_method=request.form.get("payment_method"))
            if not entry.description: raise ValueError("Informe a descrição.")
            db.session.add(entry); db.session.commit(); flash("Lançamento financeiro salvo.", "success")
            return redirect(url_for("admin.financial"))
        except (ValueError, KeyError) as error:
            db.session.rollback(); flash(str(error), "danger")
    entries = FinancialEntry.query.order_by(FinancialEntry.created_at.desc()).all()
    received = sum((Decimal(x.paid_amount or 0) for x in entries if x.kind == "RECEITA"), Decimal(0)); paid = sum((Decimal(x.paid_amount or 0) for x in entries if x.kind == "DESPESA"), Decimal(0))
    return render_template("admin/financial.html", entries=entries, received=received, paid=paid, balance=received-paid, today=date.today().isoformat())

@bp.route("/relatorios")
def reports():
    products = Product.query.filter_by(active=True).all(); projects = Project.query.all(); purchases = Purchase.query.all()
    return render_template("admin/reports.html", stock_value=sum((Decimal(x.current_quantity or 0)*Decimal(x.average_cost or 0) for x in products),Decimal(0)), low_count=sum(x.low_stock for x in products), purchase_total=sum((Decimal(x.total or 0) for x in purchases),Decimal(0)), projects=projects)

@bp.route("/<module>")
def module_page(module):
    allowed = {"compras": "Compras", "fornecedores": "Fornecedores", "clientes": "Clientes", "obras": "Obras", "financeiro": "Financeiro", "contas-pagar": "Contas a pagar", "contas-receber": "Contas a receber", "fluxo-caixa": "Fluxo de caixa", "relatorios": "Relatórios", "usuarios": "Usuários", "configuracoes": "Configurações"}
    if module not in allowed:
        return "Não encontrado", 404
    counts = {"Clientes": Customer.query.count(), "Fornecedores": Supplier.query.count(), "Obras": Project.query.count()}
    return render_template("admin/module.html", title=allowed[module], count=counts.get(allowed[module]))
