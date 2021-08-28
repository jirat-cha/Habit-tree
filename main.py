from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_bootstrap import Bootstrap
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from form import RegisterForm, LoginForm
from sqlalchemy.exc import IntegrityError
from flask_gzip import Gzip
import os
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import numpy as np

app = Flask(__name__)
gzip = Gzip(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    goal = db.Column(db.Integer)
    goal_name = db.Column(db.String(250))
    clicked = db.Column(db.String(250))
    missed_day = db.Column(db.Integer)
    left_day = db.Column(db.Integer)

db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/', methods=['POST', 'GET'])
def home():
    now = datetime.datetime.now().date()
    change = request.args.get('change_goal')
    old_goal = None
    change_goal = False
    if change:
        old_goal = request.args.get('old_goal')
        change_goal = True

    if request.method == 'POST':
        current_user.goal_name = request.form.get('goal')
        db.session.commit()
        change_goal = False
    if current_user.is_anonymous:
        login_form = LoginForm()
        register_form = RegisterForm()
        if register_form.validate_on_submit():
            new_user = User(
                email=register_form.email.data,
                password=generate_password_hash(register_form.password.data, method='pbkdf2:sha256', salt_length=8),
                name=register_form.name.data,
                goal=0,
                left_day=365,
                missed_day=0
            )
            if register_form.password.data != register_form.verify_password.data:
                flash('Invalid password')
                return redirect(url_for('home') + '#register')
            try:
                db.session.add(new_user)
                db.session.commit()
            except IntegrityError:
                flash("You've already login")
                return redirect(url_for('home') + '#login')

            login_user(new_user)
            return redirect(url_for('home'))


        if login_form.validate_on_submit():
            email = login_form.email.data
            user = User.query.filter_by(email=email).first()
            if user:
                if check_password_hash(user.password, login_form.password.data):
                    login_user(user)
                    return redirect(url_for('home'))
                else:
                    flash('Invalid password')
            else:
                flash('Invalid email')
        return render_template('login.html', registerform=register_form, loginform=login_form, year=now.year)
    else:
        if (current_user.goal_name or current_user.left_day != 365) and current_user.clicked:
            cdate = current_user.clicked.split('-')
            year, month, date = int(cdate[0]), int(cdate[1]), int(cdate[2])
            delta_date = str(now - datetime.datetime(year, month, date).date()).split()[0]
            if delta_date == '0:00:00':
                delta_date = 0
            else:
                delta_date = int(delta_date)
            current_user.left_day -= delta_date
            if delta_date > 1:
                current_user.missed_day += delta_date - 1
            db.session.commit()

    return render_template('index.html', year=now.year, now=str(now), old_goal=old_goal, change_goal=change_goal,
                           days=list(range(1, 366-current_user.left_day)),
                           flower=url_for('static', filename=f"images/flower/flower{current_user.goal%7 + 1}.png"),
                           tree=url_for('static', filename=f"images/tree/tree{current_user.goal+1}.png"), favicon=url_for('static', filename=f'habit-tree-favicon/tree{current_user.goal+1}'))


@app.route('/#logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/patch_goal')
@login_required
def patch_goal():
    current_user.goal += 1
    current_user.clicked = datetime.datetime.now().date()
    current_user.left_day -= 1
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/patch_goal_name', methods=['POST'])
@login_required
def patch_goal_name():
    old_goal = current_user.goal_name
    current_user.goal_name = None
    db.session.commit()
    return redirect(url_for('home', change_goal=True, old_goal=old_goal))


@app.route('/get_linear_coef', methods=['GET'])
def linear_regression():
    x = np.array(eval(request.args.get('x'))).transpose()
    y = eval(request.args.get('y'))
    regressor = LinearRegression()
    regressor.fit(x, y)
    result = {
        'coef': regressor.coef_.tolist(),
        'y-int': regressor.intercept_.tolist(),
        'r-square': regressor.score(x, y).tolist(),
    }
    return jsonify(result)


@app.route('/get_poly_coef', methods=['GET'])
def poly_regression():
    x = np.array(eval(request.args.get('x'))).transpose()
    y = eval(request.args.get('y'))
    degree = request.args.get('degree')
    x_poly = PolynomialFeatures(degree=degree, include_bias=False).fit_transform(x)

    regressor = LinearRegression()
    regressor.fit(x_poly, y)

    result = {
        'coef': regressor.coef_.tolist(),
        'y-int': regressor.intercept_.tolist(),
        'r-square': regressor.score(x_poly, y).tolist(),
    }

    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True)
