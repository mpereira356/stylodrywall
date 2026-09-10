from decimal import Decimal
from flask import current_app
from .extensions import db
from .models import StockMovement, AuditLog

OUT_TYPES={"Saída","Ajuste negativo","Perda","Uso em obra"}
def move_stock(product, movement_type, quantity, user=None, unit_cost=0, project=None, supplier=None, notes=None, document=None):
    amount=Decimal(str(quantity)); cost=Decimal(str(unit_cost or 0))
    if amount <= 0: raise ValueError("A quantidade deve ser maior que zero.")
    before=Decimal(product.current_quantity or 0)
    after=before-amount if movement_type in OUT_TYPES else before+amount
    if after < 0 and not current_app.config["ALLOW_NEGATIVE_STOCK"]: raise ValueError("Estoque insuficiente para esta movimentação.")
    movement=StockMovement(product=product,movement_type=movement_type,quantity=amount,previous_stock=before,resulting_stock=after,unit_cost=cost,total_cost=amount*cost,user=user,project=project,supplier_id=getattr(supplier,"id",None),notes=notes,document=document)
    product.current_quantity=after
    if movement_type=="Entrada" and cost:
        old_value=before*Decimal(product.average_cost or 0); product.last_cost=cost
        product.average_cost=(old_value+amount*cost)/(before+amount) if before+amount else cost
    db.session.add(movement); db.session.flush(); return movement
def audit(action,module,record_id,user=None,old=None,new=None,ip=None):
    db.session.add(AuditLog(action=action,module=module,record_id=str(record_id),user_id=getattr(user,"id",None),old_data=old,new_data=new,ip=ip))
