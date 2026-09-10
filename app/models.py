from datetime import datetime, timezone
from decimal import Decimal
from flask_login import UserMixin
from .extensions import db

def now(): return datetime.now(timezone.utc)
money = db.Numeric(14, 2); qty = db.Numeric(14, 3)

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True); name = db.Column(db.String(40), unique=True, nullable=False)
class User(UserMixin, db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),nullable=False); email=db.Column(db.String(180),unique=True,index=True,nullable=False); password_hash=db.Column(db.String(256),nullable=False); active=db.Column(db.Boolean,default=True); role_id=db.Column(db.Integer,db.ForeignKey("role.id"),nullable=False); role=db.relationship(Role)
    @property
    def is_active(self): return self.active
class Unit(db.Model):
    id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(12),unique=True,nullable=False); name=db.Column(db.String(60),nullable=False); active=db.Column(db.Boolean,default=True)
class Category(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(100),unique=True,nullable=False)
class Supplier(db.Model):
    id=db.Column(db.Integer,primary_key=True); company_name=db.Column(db.String(160),nullable=False); document=db.Column(db.String(20),index=True); phone=db.Column(db.String(30)); email=db.Column(db.String(180)); address=db.Column(db.Text); specialty=db.Column(db.String(180)); notes=db.Column(db.Text); active=db.Column(db.Boolean,default=True)
class Customer(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(160),nullable=False,index=True); document=db.Column(db.String(20)); phone=db.Column(db.String(30)); whatsapp=db.Column(db.String(30)); email=db.Column(db.String(180)); address=db.Column(db.Text); notes=db.Column(db.Text)
class Product(db.Model):
    id=db.Column(db.Integer,primary_key=True); internal_code=db.Column(db.String(40),unique=True,nullable=False,index=True); sku=db.Column(db.String(60)); barcode=db.Column(db.String(60)); name=db.Column(db.String(160),nullable=False,index=True); description=db.Column(db.Text); category_id=db.Column(db.Integer,db.ForeignKey("category.id"),nullable=False); unit_id=db.Column(db.Integer,db.ForeignKey("unit.id"),nullable=False); current_quantity=db.Column(qty,nullable=False,default=0); minimum_stock=db.Column(qty,nullable=False,default=0); maximum_stock=db.Column(qty); piece_length=db.Column(qty); piece_width=db.Column(qty); piece_height=db.Column(qty); coverage_area=db.Column(qty); average_cost=db.Column(money,nullable=False,default=0); last_cost=db.Column(money,nullable=False,default=0); estimated_price=db.Column(money); supplier_id=db.Column(db.Integer,db.ForeignKey("supplier.id")); location=db.Column(db.String(100)); notes=db.Column(db.Text); active=db.Column(db.Boolean,default=True); created_at=db.Column(db.DateTime(timezone=True),default=now); updated_at=db.Column(db.DateTime(timezone=True),default=now,onupdate=now); category=db.relationship(Category); unit=db.relationship(Unit); supplier=db.relationship(Supplier)
    @property
    def low_stock(self): return self.current_quantity <= self.minimum_stock
class Project(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(160),nullable=False); customer_id=db.Column(db.Integer,db.ForeignKey("customer.id")); address=db.Column(db.Text); start_date=db.Column(db.Date); expected_end=db.Column(db.Date); completed_at=db.Column(db.Date); status=db.Column(db.String(30),default="Orçamento"); sale_value=db.Column(money,default=0); labor_cost=db.Column(money,default=0); other_cost=db.Column(money,default=0); customer=db.relationship(Customer)
    materials=db.relationship("ProjectMaterial",back_populates="project",lazy=True)
    @property
    def material_cost(self): return sum((Decimal(x.total_cost or 0) for x in self.materials),Decimal(0))
    @property
    def total_cost(self): return self.material_cost+Decimal(self.labor_cost or 0)+Decimal(self.other_cost or 0)
    @property
    def estimated_profit(self): return Decimal(self.sale_value or 0)-self.total_cost
class StockMovement(db.Model):
    id=db.Column(db.Integer,primary_key=True); product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False,index=True); movement_type=db.Column(db.String(30),nullable=False); quantity=db.Column(qty,nullable=False); previous_stock=db.Column(qty,nullable=False); resulting_stock=db.Column(qty,nullable=False); unit_cost=db.Column(money,default=0); total_cost=db.Column(money,default=0); supplier_id=db.Column(db.Integer,db.ForeignKey("supplier.id")); project_id=db.Column(db.Integer,db.ForeignKey("project.id")); user_id=db.Column(db.Integer,db.ForeignKey("user.id")); document=db.Column(db.String(80)); notes=db.Column(db.Text); created_at=db.Column(db.DateTime(timezone=True),default=now,index=True); product=db.relationship(Product); project=db.relationship(Project); user=db.relationship(User)
class FinancialEntry(db.Model):
    id=db.Column(db.Integer,primary_key=True); kind=db.Column(db.String(10),nullable=False); description=db.Column(db.String(180),nullable=False); category=db.Column(db.String(80)); amount=db.Column(money,nullable=False); paid_amount=db.Column(money,nullable=False,default=0); due_date=db.Column(db.Date,index=True); paid_at=db.Column(db.Date); status=db.Column(db.String(20),default="Pendente"); payment_method=db.Column(db.String(30)); customer_id=db.Column(db.Integer,db.ForeignKey("customer.id")); supplier_id=db.Column(db.Integer,db.ForeignKey("supplier.id")); project_id=db.Column(db.Integer,db.ForeignKey("project.id")); created_at=db.Column(db.DateTime(timezone=True),default=now)
    @property
    def balance(self): return Decimal(self.amount or 0)-Decimal(self.paid_amount or 0)
class ContactRequest(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(140),nullable=False); phone=db.Column(db.String(30),nullable=False); whatsapp=db.Column(db.String(30)); email=db.Column(db.String(180)); service_type=db.Column(db.String(100)); description=db.Column(db.Text,nullable=False); location=db.Column(db.String(200)); notes=db.Column(db.Text); status=db.Column(db.String(20),default="Novo"); created_at=db.Column(db.DateTime(timezone=True),default=now,index=True)
class Service(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(140),nullable=False); description=db.Column(db.Text,nullable=False); icon=db.Column(db.String(40),default="bi-tools"); active=db.Column(db.Boolean,default=True); position=db.Column(db.Integer,default=0)
class AuditLog(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id")); action=db.Column(db.String(80),nullable=False); module=db.Column(db.String(60),nullable=False); record_id=db.Column(db.String(40)); ip=db.Column(db.String(45)); old_data=db.Column(db.JSON); new_data=db.Column(db.JSON); created_at=db.Column(db.DateTime(timezone=True),default=now,index=True)

class Purchase(db.Model):
    id=db.Column(db.Integer,primary_key=True); supplier_id=db.Column(db.Integer,db.ForeignKey("supplier.id"),nullable=True); document=db.Column(db.String(80)); purchase_date=db.Column(db.Date,nullable=False); freight=db.Column(money,default=0); discount=db.Column(money,default=0); total=db.Column(money,nullable=False,default=0); notes=db.Column(db.Text); created_at=db.Column(db.DateTime(timezone=True),default=now); user_id=db.Column(db.Integer,db.ForeignKey("user.id")); supplier=db.relationship(Supplier); user=db.relationship(User); items=db.relationship("PurchaseItem",back_populates="purchase",cascade="all, delete-orphan")
class PurchaseItem(db.Model):
    id=db.Column(db.Integer,primary_key=True); purchase_id=db.Column(db.Integer,db.ForeignKey("purchase.id"),nullable=False); product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False); quantity=db.Column(qty,nullable=False); unit_cost=db.Column(money,nullable=False); total=db.Column(money,nullable=False); purchase=db.relationship(Purchase,back_populates="items"); product=db.relationship(Product)
class ProjectMaterial(db.Model):
    id=db.Column(db.Integer,primary_key=True); project_id=db.Column(db.Integer,db.ForeignKey("project.id"),nullable=False); product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False); quantity=db.Column(qty,nullable=False); unit_cost=db.Column(money,nullable=False); total_cost=db.Column(money,nullable=False); created_at=db.Column(db.DateTime(timezone=True),default=now); project=db.relationship(Project,back_populates="materials"); product=db.relationship(Product)
class Sale(db.Model):
    id=db.Column(db.Integer,primary_key=True); customer_id=db.Column(db.Integer,db.ForeignKey("customer.id")); sale_date=db.Column(db.Date,nullable=False); payment_method=db.Column(db.String(30)); status=db.Column(db.String(20),default="Pago"); total=db.Column(money,nullable=False,default=0); notes=db.Column(db.Text); created_at=db.Column(db.DateTime(timezone=True),default=now); user_id=db.Column(db.Integer,db.ForeignKey("user.id")); customer=db.relationship(Customer); user=db.relationship(User); items=db.relationship("SaleItem",back_populates="sale",cascade="all, delete-orphan")
class SaleItem(db.Model):
    id=db.Column(db.Integer,primary_key=True); sale_id=db.Column(db.Integer,db.ForeignKey("sale.id"),nullable=False); product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False); quantity=db.Column(qty,nullable=False); unit_price=db.Column(money,nullable=False); unit_cost=db.Column(money,nullable=False,default=0); total=db.Column(money,nullable=False); sale=db.relationship(Sale,back_populates="items"); product=db.relationship(Product)
