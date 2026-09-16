from decimal import Decimal
from datetime import date
from io import BytesIO
import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Role, User, Unit, Category, Product, Purchase, PurchaseItem, FinancialEntry, StockMovement, Customer, Project, ProjectMaterial, ContactRequest, QuoteItem
from app.services import move_stock
from app.admin.routes import decimal_field

@pytest.fixture()
def app():
    app=create_app(TestConfig)
    with app.app_context(): db.create_all(); yield app; db.drop_all()

def product():
    role=Role(name="ADMINISTRADOR"); user=User(name="Teste",email="teste@stylo.local",password_hash="x",role=role)
    unit=Unit(code="M",name="Metro"); category=Category(name="Canaletas")
    item=Product(internal_code="CAN-48",name="Canaleta 48mm",unit=unit,category=category,current_quantity=Decimal("10.500"),minimum_stock=Decimal("2"))
    db.session.add_all([role,user,unit,category,item]); db.session.commit(); return item,user

def test_public_and_admin_protection(app):
    client=app.test_client()
    home = client.get("/")
    assert home.status_code==200
    assert "Baixar aplicativo" in home.get_data(as_text=True)
    assert client.get("/admin/").status_code==302
    apk = client.get("/baixar-aplicativo")
    assert apk.status_code == 200
    assert apk.data.startswith(b"PK")
    assert "stylo-gestao.apk" in apk.headers["Content-Disposition"]

def test_quote_pdf_is_downloadable(app):
    with app.app_context():
        _, user = product()
        quote = ContactRequest(name="Cliente Teste", phone="11999999999", email="cliente@example.com", service_type="Forro", description="Forro de drywall na sala", location="São Paulo", status="Novo")
        db.session.add(quote); db.session.commit()
        quote_id, user_id, product_id = quote.id, user.id, Product.query.one().id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    add_response = client.post(f"/admin/orcamentos/{quote_id}", data={"product_id": str(product_id), "quantity": "3", "unit_price": "25,50"})
    assert add_response.status_code == 302
    with app.app_context():
        item = QuoteItem.query.one()
        assert item.total == Decimal("76.50")

    response = client.get(f"/admin/orcamentos/{quote_id}/pdf")
    assert response.status_code == 200, response.headers.get("Location")
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert "attachment;" in response.headers["Content-Disposition"]
    assert f"orcamento-{quote_id}.pdf" in response.headers["Content-Disposition"]

def test_admin_can_create_quote(app):
    with app.app_context():
        _, user = product()
        customer = Customer(name="Maria Cliente", phone="11988887777", whatsapp="11988887777", email="maria@example.com", address="Rua Exemplo, 100")
        db.session.add(customer); db.session.commit()
        user_id = user.id
        customer_id = customer.id
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    response = client.post("/admin/orcamentos/novo", data={
        "customer_id": str(customer_id), "name": "", "phone": "", "whatsapp": "",
        "email": "", "service_type": "Drywall", "location": "",
        "description": "Parede de drywall para o quarto",
        "notes": "Visita pela manhã",
    })
    assert response.status_code == 302
    with app.app_context():
        quote = ContactRequest.query.one()
        assert quote.name == "Maria Cliente"
        assert quote.location == "Rua Exemplo, 100"

def test_admin_can_delete_quote_and_its_items(app):
    with app.app_context():
        item, user = product()
        quote = ContactRequest(name="Cliente", phone="11999999999", description="Orçamento para parede")
        quote_item = QuoteItem(quote=quote, product=item, quantity=Decimal("2"), unit_price=Decimal("15"), total=Decimal("30"))
        db.session.add_all([quote, quote_item]); db.session.commit()
        quote_id, user_id = quote.id, user.id
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    response = client.post(f"/admin/orcamentos/{quote_id}/remover")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(ContactRequest, quote_id) is None
        assert QuoteItem.query.count() == 0

def test_database_backup_can_be_exported_and_restored(tmp_path):
    database_path = tmp_path / "backup-test.db"
    class FileDatabaseConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
    backup_app = create_app(FileDatabaseConfig)
    with backup_app.app_context():
        db.create_all()
        role = Role(name="ADMINISTRADOR")
        user = User(name="Backup", email="backup@stylo.local", password_hash="x", role=role)
        db.session.add_all([role, user]); db.session.commit()
        user_id = user.id
    client = backup_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    exported = client.get("/admin/relatorios/banco/exportar")
    assert exported.status_code == 200
    assert exported.data.startswith(b"SQLite format 3")
    with backup_app.app_context():
        db.session.add(Customer(name="Dado posterior ao backup")); db.session.commit()
        assert Customer.query.count() == 1
    restored = client.post("/admin/relatorios/banco/importar", data={"backup": (BytesIO(exported.data), "copia.db")}, content_type="multipart/form-data")
    assert restored.status_code == 302
    with backup_app.app_context():
        assert Customer.query.count() == 0
        db.session.remove(); db.drop_all()

def test_stock_movement_and_history(app):
    with app.app_context():
        item,user=product(); movement=move_stock(item,"Saída",Decimal("2.250"),user)
        db.session.commit()
        assert item.current_quantity==Decimal("8.250")
        assert movement.previous_stock==Decimal("10.500")
        assert movement.resulting_stock==Decimal("8.250")

def test_negative_stock_is_blocked(app):
    with app.app_context():
        item,user=product()
        with pytest.raises(ValueError): move_stock(item,"Saída",Decimal("99"),user)

def test_brazilian_number_format_distinguishes_decimal_and_thousands(app):
    with app.test_request_context(method="POST", data={
        "integer":"12", "decimal":"12,5", "thousands":"12.000",
        "millions":"1.234.567", "money":"1.234,56",
    }):
        assert decimal_field("integer") == Decimal("12")
        assert decimal_field("decimal") == Decimal("12.5")
        assert decimal_field("thousands") == Decimal("12000")
        assert decimal_field("millions") == Decimal("1234567")
        assert decimal_field("money") == Decimal("1234.56")

def test_purchase_accepts_blank_optional_dimensions(app):
    with app.app_context():
        role=Role(name="ADMINISTRADOR")
        user=User(name="Teste",email="teste@stylo.local",password_hash="x",role=role)
        unit=Unit(code="UN",name="Unidade")
        category=Category(name="Placas")
        db.session.add_all([role,user,unit,category]); db.session.commit()
        user_id, unit_id, category_id = user.id, unit.id, category.id

    client=app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response=client.post("/admin/compras",data={
        "product_name":"Placa teste",
        "unit_id":str(unit_id),
        "category_id":str(category_id),
        "quantity":"2",
        "unit_cost":"10,50",
        "sale_price":"",
        "minimum_stock":"",
        "piece_length":"",
        "piece_width":"",
        "piece_height":"",
        "purchase_date":"2026-09-10",
    })

    assert response.status_code == 302
    with app.app_context():
        assert Purchase.query.count() == 1
        created = Product.query.filter_by(name="Placa teste").one()
        assert created.piece_height is None
        assert created.current_quantity == Decimal("2.000")

def test_purchase_rejects_duplicate_product_name(app):
    with app.app_context():
        existing, user = product()
        user_id = user.id
        unit_id = existing.unit_id
        category_id = existing.category_id

    client=app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response=client.post("/admin/compras",data={
        "product_name":"  canaleta   48MM ",
        "unit_id":str(unit_id),
        "category_id":str(category_id),
        "quantity":"1",
        "unit_cost":"5",
        "purchase_date":"2026-09-10",
    })

    assert response.status_code == 200
    assert "Já existe um produto cadastrado com esse nome" in response.get_data(as_text=True)
    with app.app_context():
        assert Product.query.count() == 1
        assert Purchase.query.count() == 0

def test_edit_and_delete_purchase_adjust_stock_and_financial(app):
    with app.app_context():
        item, user = product()
        purchase = Purchase(purchase_date=date(2026, 9, 10), total=Decimal("50"), user=user)
        line = PurchaseItem(purchase=purchase, product=item, quantity=Decimal("5"), unit_cost=Decimal("10"), total=Decimal("50"))
        entry = FinancialEntry(kind="DESPESA", description="Compra #1 - Compra sem fornecedor", category="Compra de material", amount=Decimal("50"), paid_amount=Decimal("50"), status="Pago")
        db.session.add_all([purchase, line, entry]); db.session.commit()
        purchase_id, user_id = purchase.id, user.id

    client=app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    edit_page=client.get(f"/admin/compras/{purchase_id}/editar").get_data(as_text=True)
    assert 'name="quantity" inputmode="decimal" value="5"' in edit_page
    assert 'name="unit_cost" inputmode="decimal" value="10,00"' in edit_page

    response=client.post(f"/admin/compras/{purchase_id}/editar",data={
        "quantity":"7", "unit_cost":"12", "purchase_date":"2026-09-11",
        "document":"NF-10", "notes":"Compra corrigida",
    })
    assert response.status_code == 302
    with app.app_context():
        purchase = db.session.get(Purchase, purchase_id)
        assert purchase.total == Decimal("84.00")
        assert purchase.items[0].product.current_quantity == Decimal("12.500")
        purchase_financial = FinancialEntry.query.filter(FinancialEntry.description.like(f"Compra #{purchase_id} -%" )).one()
        assert purchase_financial.amount == Decimal("84.00")

    response=client.post(f"/admin/compras/{purchase_id}/remover")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Purchase, purchase_id) is None
        assert Product.query.one().current_quantity == Decimal("5.500")
        assert FinancialEntry.query.filter(FinancialEntry.description.like(f"Compra #{purchase_id} -%" )).count() == 0
        assert StockMovement.query.filter(StockMovement.notes.like(f"%compra #{purchase_id}%" )).count() == 0

def test_edit_product_updates_all_data_and_regenerates_code(app):
    with app.app_context():
        item, user = product()
        old_code, user_id, unit_id, category_id = item.internal_code, user.id, item.unit_id, item.category_id

    client=app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response=client.post(f"/admin/estoque/produto/{old_code}/editar",data={
        "name":"Perfil Guia 48 mm", "category_id":str(category_id), "unit_id":str(unit_id),
        "current_quantity":"25", "minimum_stock":"3,5", "maximum_stock":"50", "sale_price":"19,90",
        "piece_length":"3", "piece_width":"0,048", "piece_height":"0,01",
        "location":"Prateleira A", "description":"Perfil metálico", "active":"1",
    })
    assert response.status_code == 302
    with app.app_context():
        updated = Product.query.one()
        assert updated.name == "Perfil Guia 48 mm"
        assert updated.internal_code != old_code
        assert updated.internal_code.startswith("CAN-PERGUI-300X4-")
        assert updated.estimated_price == Decimal("19.90")
        assert updated.minimum_stock == Decimal("3.500")
        assert updated.current_quantity == Decimal("25.000")
        assert StockMovement.query.filter_by(product_id=updated.id, movement_type="Ajuste positivo").count() == 1

def test_delete_product_removes_balance_and_history(app):
    with app.app_context():
        item, user = product()
        move_stock(item, "Entrada", Decimal("2"), user, Decimal("5"), notes="Entrada de teste")
        db.session.commit()
        code, product_id, user_id = item.internal_code, item.id, user.id

    client=app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response=client.post(f"/admin/estoque/produto/{code}/remover",follow_redirects=True)
    assert "todos os registros relacionados foram excluídos" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Product, product_id) is None
        assert StockMovement.query.filter_by(product_id=product_id).count() == 0

def test_project_material_edit_remove_and_project_delete_sync_stock(app):
    with app.app_context():
        item, user = product()
        item.average_cost = Decimal("4")
        customer = Customer(name="Cliente")
        project = Project(name="Obra teste", customer=customer, start_date=date(2026, 9, 10), sale_value=1000, labor_cost=100, other_cost=50)
        db.session.add_all([customer, project]); db.session.commit()
        project_id, product_id, user_id = project.id, item.id, user.id

    client=app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response=client.post(f"/admin/obras/{project_id}",data={"product_id":str(product_id),"quantity":"3"})
    assert response.status_code == 302
    with app.app_context():
        material = ProjectMaterial.query.one()
        material_id = material.id
        assert material.total_cost == Decimal("12.00")
        assert db.session.get(Product, product_id).current_quantity == Decimal("7.500")

    response=client.post(f"/admin/obras/{project_id}/materiais/{material_id}/editar",data={"quantity":"5"})
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Product, product_id).current_quantity == Decimal("5.500")
        assert db.session.get(ProjectMaterial, material_id).total_cost == Decimal("20.00")

    response=client.post(f"/admin/obras/{project_id}/materiais/{material_id}/remover")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Product, product_id).current_quantity == Decimal("10.500")
        assert db.session.get(ProjectMaterial, material_id) is None

    response=client.post(f"/admin/obras/{project_id}",data={"product_id":str(product_id),"quantity":"2"})
    assert response.status_code == 302
    response=client.post(f"/admin/obras/{project_id}/remover")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Project, project_id) is None
        assert db.session.get(Product, product_id).current_quantity == Decimal("10.500")
        assert StockMovement.query.filter_by(project_id=project_id).count() == 0

def test_complete_project_sets_status_and_completion_date(app):
    with app.app_context():
        _, user = product()
        customer = Customer(name="Cliente")
        project = Project(name="Obra para concluir", customer=customer, start_date=date(2026, 9, 10), status="Em andamento")
        db.session.add_all([customer, project]); db.session.commit()
        project_id, user_id = project.id, user.id

    client=app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    response=client.post(f"/admin/obras/{project_id}/concluir")
    assert response.status_code == 302
    with app.app_context():
        completed = db.session.get(Project, project_id)
        assert completed.status == "Concluída"
        assert completed.completed_at == date.today()
