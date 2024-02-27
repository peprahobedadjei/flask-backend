from flask_sqlalchemy import SQLAlchemy
from uuid import uuid4

db = SQLAlchemy()

def get_uuid():
    return uuid4().hex

class Outlet(db.Model):
    __tablename__ = "outlets"
    id = db.Column(db.String(11), primary_key=True, unique=True, default=get_uuid)
    outletName = db.Column(db.String(255), unique=True)
    outletOwnerName = db.Column(db.String(255), unique=True)
    landMark = db.Column(db.String(255), unique=True)
    outletPhoneNumber = db.Column(db.String(255), unique=True)
    outletPassword = db.Column(db.Text, nullable=False)
    outletUrl = db.Column(db.String(900), unique=True)

class OutletReviews(db.Model):
    __tablename__ = "outletReviews"
    id = db.Column(db.String(11), primary_key=True, unique=True, default=get_uuid)
    outletName = db.Column(db.String(255), nullable=False)
    question_1 = db.Column(db.String(255), nullable=False)
    question_2 = db.Column(db.String(255), nullable=False)
    question_3 = db.Column(db.String(255), nullable=False)
    question_4 = db.Column(db.String(255), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    
    
class ClientReviews(db.Model):
    __tablename__ = "clientReviews"
    id = db.Column(db.String(11), primary_key=True, unique=True, default=get_uuid)
    clientName = db.Column(db.String(255), nullable=False)
    question_1 = db.Column(db.String(255), nullable=False)
    question_2 = db.Column(db.String(255), nullable=False)
    question_3 = db.Column(db.String(255), nullable=False)

