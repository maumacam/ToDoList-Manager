from flask import Flask, render_template, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Initialize LoginManager
login_manager = LoginManager(app)
login_manager.login_view = "login"  # Redirect to login page if user is not authenticated

# Define the user_loader callback function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Store password as a hash

    def __repr__(self):
        return f'<User {self.username}>'

    # Required methods for Flask-Login
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)  # Flask-Login expects this to return a string

# Task Model
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False)
    due_date = db.Column(db.DateTime)  # Make sure this is defined
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    user = db.relationship('User', backref='tasks', lazy=True)

    def __repr__(self):
        return f'<Task {self.id}: {self.done}>'
    
@app.route('/')
def home():
    if current_user.is_authenticated:  # Check if the user is logged in
        return redirect('/index')  # Redirect to tasks page
    return redirect('/register')  # Redirect to the registration page

# Routes for Authentication
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if the username or email is already taken
        if User.query.filter_by(username=username).first():
            flash("Username already exists. Please choose another one.", "danger")
            return redirect('/register')
        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please log in.", "danger")
            return redirect('/login')

        # Correct hashing method
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful! Please log in.", "success")
        return redirect('/login')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()

        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                flash("Login successful!", "success")
                return redirect('/index')
            else:
                flash("Login failed. Incorrect password.", "danger")
        else:
            flash("Username does not exist. Please register.", "danger")
            return redirect('/register')  # Redirect to the registration page
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have logged out.", "success")
    return redirect('/login')

# Routes for Task Management
@app.route('/index')
@login_required
def tasks_list():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', tasks=tasks)

@app.route('/task', methods=['POST'])
@login_required
def add_task():
    content = request.form['content']
    due_date = request.form['due_date']
    
    if not content:
        flash('Please enter text for your task', "danger")
        return redirect('/index')
    
    # Parse due_date as a datetime object
    try:
        due_date_obj = datetime.strptime(due_date, '%Y-%m-%d')  # Ensure the format matches the input
    except ValueError:
        flash('Invalid date format. Please use YYYY-MM-DD.', "danger")
        return redirect('/index')
    
    task = Task(content=content, user_id=current_user.id, due_date=due_date_obj)
    db.session.add(task)
    db.session.commit()
    flash("Task added successfully!", "success")
    return redirect('/index')

@app.route('/toggle', methods=['POST'])
@login_required
def toggle_status():
    task_id = request.form['task_id']
    task = Task.query.get(task_id)
    if task and task.user_id == current_user.id:
        task.done = not task.done  # Toggle done status
        db.session.commit()
        flash("Task status updated.", "success")
    else:
        flash("Task not found or unauthorized action.", "danger")
    return redirect('/index')

@app.route('/edit', methods=['POST'])
@login_required
def edit_task():
    task_id = request.form['task_id']
    edit_text = request.form['edit_text']
    
    if not edit_text:
        flash('Please enter text for your task', "danger")
        return redirect('/index')
    
    task = Task.query.get(task_id)
    if task and task.user_id == current_user.id:
        task.content = edit_text
        db.session.commit()
        flash("Task updated successfully.", "success")
    else:
        flash("Task not found or unauthorized action.", "danger")
    return redirect('/index')

@app.route('/delete/<int:task_id>')
@login_required
def delete_task(task_id):
    task = Task.query.get(task_id)
    if task and task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
        flash("Task deleted successfully.", "success")
    else:
        flash("Task not found or unauthorized action.", "danger")
    return redirect('/index')

@app.route('/finished')
@login_required
def resolve_tasks():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    for task in tasks:
        if not task.done:
            task.done = True
    db.session.commit()
    flash("All tasks marked as completed.", "success")
    return redirect('/index')

@app.route('/analytics')
@login_required
def analytics():
    # Get all tasks for the current user
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    # Calculate stats
    total_tasks = len(tasks)
    completed_tasks = sum(task.done for task in tasks)
    pending_tasks = total_tasks - completed_tasks
    overdue_tasks = sum(task.due_date < datetime.now() and not task.done for task in tasks if task.due_date)

    return render_template('analytics.html', 
                           total_tasks=total_tasks, 
                           completed_tasks=completed_tasks, 
                           pending_tasks=pending_tasks, 
                           overdue_tasks=overdue_tasks)

# Initialize the database tables
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
