from flask import Flask, render_template, request, redirect, flash, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import func

app = Flask(__name__)
app.static_folder = 'static'
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = 'mykey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mystatement.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.session_protection = "strong"
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(15), unique=True)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String, nullable=False)
    gender = db.Column(db.String(15), nullable=False)
    balance = db.Column(db.Integer, default=0)
    transactions = db.relationship('Transaction', backref='user')


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(50), nullable=False)
    transaction_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    sendTo = db.Column(db.String(100))
    receiveFrom = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@app.template_filter()
def currencyFormat(value):
    value = float(value)
    return "{:,.2f}".format(value)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()


@app.route('/login', methods=['GET', 'POST'])
def login():
    isError = False
    if (current_user.is_authenticated):
        return redirect('/')
    if request.method == 'POST':
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user:
            if bcrypt.check_password_hash(user.password, password):
                login_user(user, remember=True)
                return redirect('/')
        flash('Username or password is incorrect')
        isError = True
        return render_template('login.html', isError=isError)
    return render_template('login.html', isError=isError)


@app.route('/signup', methods=['POST', 'GET'])
def signup():
    isError = False
    avatar = False
    if (current_user.is_authenticated):
        return redirect('/')
    if request.method == 'POST':
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        cf_password = request.form["cf_password"]
        gender = request.form["gender"]

        if not email or not username or not password or not cf_password or not gender:
            flash("Fields is required")
            isError = True
            return render_template('signup.html', isError=isError)
        if password != cf_password:
            flash("Password does not match")
            isError = True
            return render_template('signup.html', isError=isError)
        findUsername = User.query.filter_by(username=username).first()
        findEmail = User.query.filter_by(email=email).first()
        if findUsername:
            isError = True
            flash("Username is already exits")
            return render_template('signup.html', isError=isError)
        if findEmail:
            isError = True
            flash("Email is already exits")
            return render_template('signup.html', isError=isError)
        if gender == 'male':
            avatar = "https://res.cloudinary.com/dwiylz9ql/image/upload/v1670677569/sc-media/male_avatar_wiegpe.png"
        elif gender == 'female':
            avatar = "https://res.cloudinary.com/dwiylz9ql/image/upload/v1670677559/sc-media/female_avatar_fxepe0.png"
        password_hash = bcrypt.generate_password_hash(password)
        new_user = User(username=username, email=email,
                        password=password_hash, avatar=avatar, gender=gender)
        db.session.add(new_user)
        db.session.commit()
        flash("Signed Up Successfully")
        return redirect('/')
    return render_template('signup.html', isError=isError)


@app.route("/")
@login_required
def createForm():
    balance = db.session.query(func.sum(Transaction.amount).label("amount")).filter(
        Transaction.user_id == current_user.id).first().amount
    if not balance:
        balance = 0
    transactions_income = Transaction.query.filter(
        Transaction.user_id == current_user.id, Transaction.category == 'income').all()
    if not transactions_income:
        income = 0
    elif transactions_income:
        income = db.session.query(func.sum(Transaction.amount).label("amount")).filter(
        Transaction.user_id == current_user.id).group_by(Transaction.category == 'expense').first().amount
    transactions_expense = Transaction.query.filter(
        Transaction.user_id == current_user.id, Transaction.category == 'expense').all()
    if not transactions_expense:
        expense = 0
    elif transactions_expense:
        expense = db.session.query(func.sum(Transaction.amount).label("amount")).filter(
        Transaction.user_id == current_user.id).group_by(Transaction.category).first().amount
    
    return render_template("createForm.html", isError=request.args.get('isError'), profile=current_user, balance=balance, income=income, expense=expense)

@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", profile=current_user, isError=request.args.get('isError'))


@app.route("/transaction")
@login_required
def transaction():
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id).all()
    return render_template("transaction.html", profile=current_user, transactions=transactions, isError=request.args.get('isError'))


@app.route("/createTransaction", methods=['POST'])
@login_required
def createTransaction():
    isError = False
    date = request.form["date"]
    transaction_name = request.form["transaction_name"]
    if request.form["amount"]:
        amount = float(request.form["amount"])
        if amount < 0:
            amount = -abs(amount)
    category = request.form["category"]
    sendTo = request.form["sendTo"]
    receiveFrom = request.form["receiveFrom"]
    if not date or not transaction_name or not amount:
        flash("Fields is required")
        if amount == 0:
            flash("Amount must not be 0")
        isError = True
        return redirect(url_for('createForm', isError=isError))
        # return render_template("createForm.html", isError=isError)
    elif amount < 0 and category != 'expense':
        flash("Amount must more than 0")
        isError = True
        return redirect(url_for('createForm', isError=isError))
    elif amount > 0 and category != 'income':
        flash("Amount must less than 0")
        isError = True
        return redirect(url_for('createForm', isError=isError))
        # return redirect('/')
    if receiveFrom and sendTo:
        flash("Can not input both fields (Send to and Receive From)")
        isError = True
        return redirect(url_for('createForm', isError=isError))
        # return redirect('/')
    if (receiveFrom and amount <= 0 and category != "income") or (sendTo and amount <= 0 and category != "expense"):
        flash("Something went wrong")
        isError = True
        return redirect(url_for('createForm', isError=isError))
        # return redirect('/')
    new_transaction = Transaction(date=date, transaction_name=transaction_name,
                                  amount=request.form["amount"], category=category, sendTo=sendTo, receiveFrom=receiveFrom, user_id=current_user.id)
    db.session.add(new_transaction)
    db.session.commit()
    flash("Create Transaction Successfully")
    return redirect('/')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('createForm'))


@app.route("/delete/<int:id>")
@login_required
def deleteTransaction(id):
    isError = False
    transaction = Transaction.query.filter_by(
        id=id, user_id=current_user.id).first()
    if transaction.user_id != current_user.id:
        isError = True
        flash("Permission is denied")
        return redirect(url_for('transaction', isError=isError))
    db.session.delete(transaction)
    db.session.commit()
    flash("Deleted transaction successfully")
    return redirect(url_for('transaction', isError=isError))


@app.route("/edit/<int:id>")
@login_required
def editTransaction(id):
    isError = False
    transaction = Transaction.query.filter_by(
        id=id, user_id=current_user.id).first()
    if transaction.user_id != current_user.id:
        isError = True
        flash("Permission is denied")
        return redirect(url_for('transaction', isError=isError))
    return render_template("editForm.html", transaction=transaction, profile=current_user)


@app.route("/update/<int:id>", methods=['POST'])
@login_required
def updateTransaction(id):
    isError = False
    date = request.form["date"]
    transaction_name = request.form["transaction_name"]
    if request.form["amount"]:
        amount = float(request.form["amount"])
    else:
        flash("Amount is required")
        isError = True
        return redirect(url_for('transaction', isError=isError))
    category = request.form["category"]
    sendTo = request.form["sendTo"]
    receiveFrom = request.form["receiveFrom"]
    if not date or not transaction_name or not amount:
        flash("Fields is required")
        if amount == 0:
            flash("Amount must not be 0")
        isError = True
        return redirect(url_for('transaction', isError=isError))
        # return render_template("createForm.html", isError=isError)
    elif amount < 0 and category != 'expense':
        flash("Amount must more than 0 if category is Income")
        isError = True
        return redirect(url_for('transaction', isError=isError))
    elif amount > 0 and category != 'income':
        flash("Amount must less than 0 if category is Expense")
        isError = True
        return redirect(url_for('transaction', isError=isError))
        # return redirect('/')
    if receiveFrom and sendTo:
        flash("Can not input both fields (Send to and Receive From)")
        isError = True
        return redirect(url_for('transaction', isError=isError))
        # return redirect('/')
    if (receiveFrom and amount <= 0 and category != "income") or (sendTo and amount <= 0 and category != "expense"):
        flash("Something went wrong")
        isError = True
        return redirect(url_for('transaction', isError=isError))

    transaction = Transaction.query.filter_by(
        id=id, user_id=current_user.id).first()
    if transaction.user_id != current_user.id:
        isError = True
        flash("Permission is denied")
        return redirect(url_for('transaction', isError=isError))
    transaction.date = date
    transaction.transaction_name = transaction_name
    transaction.amount = amount
    transaction.category = category
    transaction.sendTo = sendTo
    transaction.receiveFrom = receiveFrom

    db.session.commit()

    return redirect(url_for('transaction', isError=isError))

@app.route("/updateProfile", methods=['POST'])
@login_required
def updateProfile():
    isError = False
    username = request.form["username"]
    password = request.form["password"]
    current_password = request.form["current_password"]

    if not current_password:
        isError = True
        flash("Please input your current password")
        return redirect(url_for('profile', isError=isError))
    if not username :
        isError = True
        flash("Username is required")
        return redirect(url_for('profile', isError=isError))

    findUser = User.query.filter_by(id=current_user.id).first()
    if not findUser:
        isError = True
        flash("User does not exits")
        return redirect(url_for('profile', isError=isError))
    if not bcrypt.check_password_hash(findUser.password, current_password):
            flash('Password does not match')
            isError = True
            return redirect(url_for('profile', isError=isError))
    if password:
        password_hash = bcrypt.generate_password_hash(password)
    else:
        password_hash = findUser.password
    findUser.username = username
    findUser.password = password_hash 
    
    db.session.commit()
    flash("Updated Profile Successfully")
    
    return redirect("/profile")

if (__name__) == "__main__":
    app.run(debug=True)
