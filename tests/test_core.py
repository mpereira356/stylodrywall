from decimal import Decimal
import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Role, User, Unit, Category, Product
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

