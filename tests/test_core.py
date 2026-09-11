from decimal import Decimal
import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Role, User, Unit, Category, Product, Purchase
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
