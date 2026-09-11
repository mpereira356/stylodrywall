from decimal import Decimal
from datetime import date
import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Role, User, Unit, Category, Product, Purchase, PurchaseItem, FinancialEntry, StockMovement
from app.services import move_stock

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
    assert client.get("/").status_code==200
    assert client.get("/admin/").status_code==302

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
        "minimum_stock":"3,5", "maximum_stock":"50", "sale_price":"19,90",
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
        assert updated.current_quantity == Decimal("10.500")

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
