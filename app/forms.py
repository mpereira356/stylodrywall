from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, DecimalField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange

class LoginForm(FlaskForm):
    username=StringField("Usuário",validators=[DataRequired(),Length(min=3,max=180)]); password=PasswordField("Senha",validators=[DataRequired()]); submit=SubmitField("Entrar no painel")
class ContactForm(FlaskForm):
    name=StringField("Nome",validators=[DataRequired(),Length(max=140)]); phone=StringField("Telefone",validators=[DataRequired(),Length(max=30)]); whatsapp=StringField("WhatsApp",validators=[Optional(),Length(max=30)]); email=StringField("E-mail",validators=[Optional(),Email()]); service_type=SelectField("Tipo de serviço",choices=[("Drywall","Drywall"),("Forro","Forro de gesso"),("Divisória","Divisória"),("Sanca","Sanca e tabica"),("Reforma","Reforma e acabamento"),("Outro","Outro")]); location=StringField("Local da obra",validators=[Optional(),Length(max=200)]); description=TextAreaField("Conte sobre o projeto",validators=[DataRequired(),Length(min=10,max=3000)]); notes=TextAreaField("Observações",validators=[Optional(),Length(max=1000)]); submit=SubmitField("Enviar solicitação")
class MovementForm(FlaskForm):
    product_id=SelectField("Produto",coerce=int,validators=[DataRequired()]); movement_type=SelectField("Movimentação",choices=[(x,x) for x in ["Entrada","Saída","Ajuste positivo","Ajuste negativo","Devolução","Perda","Uso em obra"]]); quantity=DecimalField("Quantidade",places=3,validators=[DataRequired(),NumberRange(min=0.001)]); unit_cost=DecimalField("Custo unitário",places=2,validators=[Optional(),NumberRange(min=0)]); notes=StringField("Observação",validators=[Optional(),Length(max=300)]); submit=SubmitField("Confirmar movimentação")
