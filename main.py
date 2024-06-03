from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from wtforms import HiddenField
from flask_wtf import FlaskForm
from datetime import datetime, timedelta
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired, NumberRange
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from twilio.rest import Client
from forms import RegShopper, RegUser, LoginAdmin, LoginUser, ShopForm, ItemForm
from flask_migrate import Migrate


app = Flask(__name__)
app.config['SECRET_KEY'] = 'SECRET KEY'
Bootstrap5(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
db = SQLAlchemy()
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)

account_sid = "TWILIO SID KEY"
auth_token = 'TWILIO AUTH KEY'


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


@login_manager.user_loader
def load_admin(admin_id):
    return db.get_or_404(Admin, admin_id)


class Admin(UserMixin, db.Model):
    __tablename__ = "admin"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    phone = db.Column(db.String(100))
    role = db.Column(db.String(50), default='admin')
    shops = db.relationship('Shop', backref='admin', lazy=True)


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    phone = db.Column(db.String(100))
    role = db.Column(db.String(50), default='user')


class Shop(db.Model):
    __tablename__ = "shop"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    items = db.relationship('Item', backref='shop', lazy=True)


# Define Item model
class Item(db.Model):
    __tablename__ = "item"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)


with app.app_context():
    db.create_all()


@app.route('/')
def home():
    return render_template("index.html")


@app.route('/register')
def register():
    return render_template("register.html")


@app.route('/regadmin', methods=["GET", "POST"])
def regadmin():
    form = RegShopper()
    if form.validate_on_submit():
        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        if len(form.phone.data) == 10:
            new_user = Admin(
                email=form.email.data,
                name=form.name.data,
                password=hash_and_salted_password,
                phone=form.phone.data
            )
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for("login"))
        else:
            flash("Phone Number should be of 10 digits")
            return redirect(url_for("regadmin"))
    return render_template("regadmin.html", form=form, current_user=current_user)


@app.route('/reguser', methods=["GET", "POST"])
def reguser():
    form = RegUser()
    if form.validate_on_submit():
        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        if len(form.phone.data) == 10:
            new_user = User(
                email=form.email.data,
                name=form.name.data,
                password=hash_and_salted_password,
                phone=form.phone.data

            )
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for("login"))
        else:
            flash("Phone Number should be of 10 digits")
            return redirect(url_for("reguser"))
    return render_template("reguser.html", form=form, current_user=current_user)


@app.route('/login')
def login():
    return render_template("login.html")


@app.route('/logadmin', methods=['GET', 'POST'])
def logadmin():
    form = LoginAdmin()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(Admin).where(Admin.email == form.email.data))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('logadmin'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('logadmin'))
        else:
            login_user(user)
            return redirect(url_for('home_admin'))

    return render_template("logadmin.html", form=form, current_user=current_user)


@app.route('/home_admin')
def home_admin():
    return render_template('home_admin.html')


@app.route('/loguser', methods=['GET', 'POST'])
def loguser():
    form = LoginUser()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('loguser'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('loguser'))
        else:
            login_user(user)
            return redirect(url_for('all_shops'))

    return render_template("loguser.html", form=form, current_user=current_user)


@app.route("/add-shop", methods=['GET', 'POST'])
@login_required
def add_shop():
    form = ShopForm()
    if form.validate_on_submit():
        shop = Shop(name=form.name.data, address=form.address.data, admin_id=current_user.id)
        db.session.add(shop)
        db.session.commit()
        return redirect(url_for('create_items', shop=shop, shop_id=shop.id))
    return render_template('add-shop.html', form=form)


@app.route('/create_items/<int:shop_id>', methods=['GET', 'POST'])
def create_items(shop_id):
    shop = db.get_or_404(Shop, shop_id)
    form = ItemForm()
    if form.validate_on_submit():
        number_of_items = form.number_of_items.data
        return redirect(url_for('fill_items', shop_id=shop.id, num_items=number_of_items))
    return render_template('create_items.html', form=form, shop=shop, shop_id=shop.id)


@app.route('/fill_items/<int:shop_id>/<int:num_items>', methods=['GET', 'POST'])
def fill_items(shop_id, num_items):
    shop = Shop.query.get_or_404(shop_id)

    # shop_id = request.args.get('shop_id')

    # num_items = request.args.get('num_items')

    class DynamicItemForm(FlaskForm):
        shop_id = HiddenField('Shop ID', default=shop.id)
        pass

    for i in range(num_items):
        setattr(DynamicItemForm, f'name_{i}', StringField(f'Item {i + 1} Name', validators=[DataRequired()]))
        setattr(DynamicItemForm, f'quantity_{i}',
                IntegerField(f'Item {i + 1} Quantity', validators=[DataRequired(), NumberRange(min=1)]))
        setattr(DynamicItemForm, f'price_{i}',
                IntegerField(f'Item {i + 1} Price', validators=[DataRequired()]))
    form = DynamicItemForm()

    if form.validate_on_submit():
        for i in range(num_items):
            item = Item(name=getattr(form, f'name_{i}').data, quantity=getattr(form, f'quantity_{i}').data,
                        price=getattr(form, f'price_{i}').data,
                        shop_id=shop.id)
            db.session.add(item)
        db.session.commit()

        return redirect(url_for('view_items', shop_id=shop.id))

    return render_template('fill_items.html', form=form, num_items=num_items, shop=shop)


@app.route('/view_items', methods=['GET'])
@login_required
def view_items():
    # Fetch all shop names associated with the currently logged-in user
    user_shops = Shop.query.filter_by(admin_id=current_user.id).all()

    # Fetch all items for the shops associated with the user
    all_items = Item.query.filter(Item.shop_id.in_([shop.id for shop in user_shops])).all()

    return render_template('view_items.html', user_shops=user_shops, all_items=all_items)


@app.route('/all_items/<int:shop_id>', methods=['GET'])
def all_items(shop_id):
    result1 = db.session.execute(db.select(Shop))
    shops = result1.scalars().all()

    # Get the selected shop based on shop_id
    selected_shop = next((shop for shop in shops if shop.id == shop_id), None)

    # Filter items based on the selected shop_id
    result2 = db.session.execute(db.select(Item).where(Item.shop_id == shop_id))
    items = result2.scalars().all()

    return render_template('all_items.html', shops=shops, items=items, selected_shop=selected_shop)

@app.route('/all_shops', methods=['GET'])
def all_shops():
    result1 = db.session.execute(db.select(Shop))
    shops = result1.scalars().all()
    return render_template('all_shops.html', shops=shops)

@app.route('/update_page/', methods=['GET', 'POST'])
def update_page():
    # Fetch all shop names associated with the currently logged-in user
    user_shops = Shop.query.filter_by(admin_id=current_user.id).all()

    # Fetch all items for the shops associated with the user

    return render_template('update_page.html', user_shops=user_shops)


@app.route('/update_items/<int:shop_id>', methods=['GET', 'POST'])
def update_items(shop_id):
    shop = Shop.query.get_or_404(shop_id)

    # Dynamically create the form class for this request
    class DynamicItemForm(FlaskForm):
        shop_id = HiddenField(default=shop.id)
        pass

    items = Item.query.filter_by(shop_id=shop.id).all()

    for i, item in enumerate(items):
        setattr(DynamicItemForm, f'name_{i}',
                StringField(f'Item {i + 1} Name', validators=[DataRequired()], default=item.name))
        setattr(DynamicItemForm, f'quantity_{i}',
                IntegerField(f'Item {i + 1} Quantity', validators=[DataRequired(), NumberRange(min=1)],
                             default=item.quantity))
        setattr(DynamicItemForm, f'price_{i}',
                IntegerField(f'Item {i + 1} Price', validators=[DataRequired()], default=item.price))
        setattr(DynamicItemForm, f'original_price_{i}', HiddenField(default=item.price))

    form = DynamicItemForm()

    if form.validate_on_submit():
        for i, item in enumerate(items):
            item_name = getattr(form, f'name_{i}').data
            item_quantity = getattr(form, f'quantity_{i}').data
            item_price = getattr(form, f'price_{i}').data
            original_price = int(getattr(form, f'original_price_{i}').data)

            # Update the existing item with the form data
            item.name = item_name
            item.quantity = item_quantity
            item.price = item_price
            if item_price < original_price:
                client = Client(account_sid, auth_token)
                message = client.messages \
                    .create(
                    body=f"The price of {item_name} is reduced from {original_price} to {item_price} at {shop.name}",
                    from_='#Your twilio number',
                    to='user phone number'
                )

        db.session.commit()
        return redirect(url_for('view_items', shop_id=shop.id))

    return render_template('update_items.html', form=form, shop=shop)


@app.route("/logout")
def logout():
    logout_user()
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True)
