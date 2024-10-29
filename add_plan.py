from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db, StoragePlan  # Adjust this import according to your structure

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_secret_key'

# Initialize the database
db.init_app(app)

def add_storage_plan(name, price, storage_limit):
    with app.app_context():
        new_plan = StoragePlan(name=name, price=price, storage_limit=storage_limit)
        db.session.add(new_plan)
        db.session.commit()
        print(f'Storage plan "{name}" added successfully!')

if __name__ == '__main__':
    # Adding the Basic Plan
    plan_name = 'Basic Plan'
    plan_price = 5.0
    plan_storage_limit = 10  
    add_storage_plan(plan_name, plan_price, plan_storage_limit)

    # Adding the Standard Plan
    plan_name = 'Standard Plan'
    plan_price = 15.0
    plan_storage_limit = 50  
    add_storage_plan(plan_name, plan_price, plan_storage_limit)

    # Adding the Premium Plan
    plan_name = 'Premium Plan'
    plan_price = 30.0
    plan_storage_limit = 200  
    add_storage_plan(plan_name, plan_price, plan_storage_limit)
