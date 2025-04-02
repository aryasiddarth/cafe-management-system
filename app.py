from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from flask import jsonify
import sqlite3
import os
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure key

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def safe_send_from_directory(directory, filename):
    directory_path = os.path.join(app.root_path, directory)
    if os.path.exists(os.path.join(directory_path, filename)):
        return send_from_directory(directory_path, filename)
    return "File not found", 404

@app.route('/css/<path:filename>')
def serve_css(filename):
    return safe_send_from_directory('css', filename)

@app.route('/img/<path:filename>')
def serve_img(filename):
    return safe_send_from_directory('img', filename)

@app.route('/scss/<path:filename>')
def serve_scss(filename):
    return safe_send_from_directory('scss', filename)

@app.route('/lib/<path:filename>')
def serve_lib(filename):
    return safe_send_from_directory('lib', filename)

@app.route('/mail/<path:filename>')
def serve_mail(filename):
    return safe_send_from_directory('mail', filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return safe_send_from_directory('js', filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/founders')
def founders():
    return render_template("founders.html")

@app.route('/login_home')
def login_home():
    return render_template("login.html")

@app.route('/menu')
def menu():
    conn = get_db_connection()
    menu_items = conn.execute('SELECT * FROM menu_items ORDER BY name').fetchall()
    conn.close()
    
    return render_template('menu_main.html', menu_items=menu_items)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return f"Welcome, {session['role'].capitalize()}! You are logged in."

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return "Login page", 200

    username = request.form.get('user_id', None)
    password = request.form.get('password', None)
    role = request.form.get('role', None)

    conn = get_db_connection()

    if role == 'customer':
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers WHERE customer_id = ? AND password = ?", (username, password))
        user = cur.fetchone()

        if user:
            session['user_id'] = user['customer_id']  # Changed from 'id' to 'customer_id'
            session['role'] = 'customer'
            return redirect(url_for('customer_dashboard'))

    elif role == 'manager':
        cur = conn.cursor()
        cur.execute("SELECT * FROM managers WHERE manager_id = ? AND password = ?", (username, password))
        user = cur.fetchone()

        if user:
            session['user_id'] = user['manager_id']
            session['role'] = 'manager'
            return redirect(url_for('manager_dashboard'))

    elif role == 'waiter':
        cur = conn.cursor()
        cur.execute("SELECT * FROM waiters WHERE waiter_id = ? AND password = ?", (username, password))
        user = cur.fetchone()

        if user:
            session['user_id'] = user['waiter_id']
            session['role'] = 'waiter'
            return redirect(url_for('waiter_dashboard'))

    conn.close()
    return "Invalid credentials! Try again.", 401

import json  # Add this at the top with other imports

@app.route('/new_order')
def new_order():
    if 'user_id' not in session or session.get('role') != 'customer':
        flash('Please login to place an order', 'danger')
        return redirect(url_for('login'))
    
    conn = None
    try:
        conn = get_db_connection()
        menu_items = conn.execute('SELECT * FROM menu_items ORDER BY name').fetchall()
        return render_template('new_order.html', menu_items=menu_items)
    except Exception as e:
        print(f"Error loading menu: {e}")
        flash('Error loading menu items', 'danger')
        return redirect(url_for('customer_dashboard'))
    finally:
        if conn:
            conn.close()

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session or session.get('role') != 'customer':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = None
    try:
        order_data = request.form.get('order_data')
        if not order_data:
            return jsonify({'success': False, 'message': 'No order data received'}), 400
        
        items = json.loads(order_data)
        if not items:
            return jsonify({'success': False, 'message': 'No items in order'}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verify all items exist
        valid_item_ids = {row['item_id'] for row in conn.execute('SELECT item_id FROM menu_items').fetchall()}
        for item_id in items.keys():
            if int(item_id) not in valid_item_ids:
                return jsonify({'success': False, 'message': f'Invalid item ID: {item_id}'}), 400
        
        # Create order
        cur.execute('INSERT INTO orders (customer_id) VALUES (?)', (session['user_id'],))
        order_id = cur.lastrowid
        
        # Add order items
        for item_id, item in items.items():
            cur.execute('''
                INSERT INTO order_items (order_id, item_id, quantity)
                VALUES (?, ?, ?)
            ''', (order_id, item_id, item['quantity']))
        
        conn.commit()
        return jsonify({
            'success': True, 
            'message': 'Order placed successfully',
            'order_id': order_id
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': 'Invalid data format'}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error placing order: {e}")
        return jsonify({'success': False, 'message': 'Database error occurred'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/order_history')
def order_history():
    if 'user_id' in session and session['role'] == 'customer':
        return render_template("order_history.html")
    else:
        return redirect(url_for('login_home'))

@app.route('/account')
def account():
    if 'user_id' not in session or session.get('role') != 'customer':
        flash('Please login to view account information', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        customer = conn.execute('''
            SELECT customer_id, username, email, contact, created_at as join_date
            FROM customers
            WHERE customer_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not customer:
            flash('Account not found', 'danger')
            return redirect(url_for('customer_dashboard'))
            
        return render_template('view_account.html', customer=customer)
        
    except Exception as e:
        print(f"Error loading account: {e}")
        flash('Error loading account information', 'danger')
        return redirect(url_for('customer_dashboard'))
    finally:
        conn.close()
    
@app.route('/waiter_dashboard')
def waiter_dashboard():
    if 'user_id' in session and session['role'] == 'waiter':
        return render_template("waiter_dashboard.html")
    else:
        return redirect(url_for('login_home'))
    
@app.route('/manager_dashboard')
def manager_dashboard():
    if 'user_id' not in session or session.get('role') != 'manager':
        return redirect(url_for('login_home'))
    return render_template("manager_dashboard.html")
    
@app.route('/customer_dashboard')
def customer_dashboard():
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('login'))  # Redirect if not logged in

    conn = get_db_connection()
    cur = conn.cursor()
    
    # Fetch username (since there is no "name" column)
    cur.execute("SELECT username FROM customers WHERE customer_id = ?", (session['user_id'],))
    user = cur.fetchone()
    conn.close()

    if user:
        return render_template("customer_dashboard.html", customer_name=user['username'])
    else:
        return "User not found!", 404


@app.route('/menu_customer')
def menu_customer():
    if 'customer_id' not in session:
        return redirect(url_for('login'))
    # Logic to handle new orders
    return render_template('menu.html')

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session or session.get('role') != 'customer':
        return redirect(url_for('login'))
    
    item_id = request.form.get('item_id')
    quantity = request.form.get('quantity', 1, type=int)
    
    # Initialize cart in session if it doesn't exist
    if 'cart' not in session:
        session['cart'] = {}
    
    # Add item to cart or update quantity
    cart = session['cart']
    cart[item_id] = cart.get(item_id, 0) + quantity
    session['cart'] = cart
    
    return redirect(url_for('menu'))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Add this helper function
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/edit_menu')
def edit_menu():
    if 'user_id' not in session or session.get('role') != 'manager':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        menu_items = conn.execute('SELECT * FROM menu_items ORDER BY item_id').fetchall()
        return render_template('edit_menu.html', menu_items=menu_items)
    except Exception as e:
        print(f"Error loading menu: {e}")
        flash('Error loading menu items', 'danger')
        return redirect(url_for('manager_dashboard'))
    finally:
        conn.close()

@app.route('/add_menu_item', methods=['POST'])
def add_menu_item():
    if 'user_id' not in session or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '').strip()
        
        if not name or not price:
            return jsonify({'success': False, 'message': 'Name and price are required'}), 400
        
        try:
            price = float(price)
            if price <= 0:
                return jsonify({'success': False, 'message': 'Price must be positive'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid price format'}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert new item
        cur.execute('INSERT INTO menu_items (name, price) VALUES (?, ?)', (name, price))
        item_id = cur.lastrowid
        
        # Handle file upload if present
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = f'item-{item_id}.jpg'
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Item added successfully'})
        
    except Exception as e:
        print(f"Error adding menu item: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/edit_menu_item', methods=['POST'])
def edit_menu_item():
    if 'user_id' not in session or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        item_id = request.form.get('item_id', '').strip()
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '').strip()
        
        if not all([item_id, name, price]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        try:
            price = float(price)
            if price <= 0:
                return jsonify({'success': False, 'message': 'Price must be positive'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid price format'}), 400

        conn = get_db_connection()
        conn.execute('UPDATE menu_items SET name = ?, price = ? WHERE item_id = ?', 
                    (name, price, item_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Item updated successfully'})
        
    except Exception as e:
        print(f"Error updating menu item: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/delete_menu_item', methods=['POST'])
def delete_menu_item():
    if 'user_id' not in session or session.get('role') != 'manager':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        item_id = request.form.get('item_id', '').strip()
        if not item_id:
            return jsonify({'success': False, 'message': 'Item ID is required'}), 400

        conn = get_db_connection()
        
        # Delete associated image if exists
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], f'item-{item_id}.jpg')
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                print(f"Error deleting image: {e}")
        
        # Delete from database
        conn.execute('DELETE FROM menu_items WHERE item_id = ?', (item_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Item deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting menu item: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()


@app.route('/customer_orders')
def customer_orders():
    if 'user_id' not in session or session.get('role') not in ['manager', 'waiter']:
        flash('You do not have permission to view this page', 'danger')
        return redirect(url_for('login_home'))
    
    conn = get_db_connection()
    try:
        # Get orders with customer names and totals
        orders = conn.execute('''
            SELECT o.order_id, c.username as customer_name, 
                   o.order_date, SUM(mi.price * oi.quantity) as total_amount
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN menu_items mi ON oi.item_id = mi.item_id
            GROUP BY o.order_id
            ORDER BY o.order_date DESC
        ''').fetchall()
        
        # Get order items with names and calculated totals
        order_items = conn.execute('''
            SELECT oi.order_id, mi.name as item_name, 
                   oi.quantity, mi.price, 
                   (mi.price * oi.quantity) as item_total
            FROM order_items oi
            JOIN menu_items mi ON oi.item_id = mi.item_id
            ORDER BY oi.order_id
        ''').fetchall()
        
        # Get all customers (without passwords)
        customers = conn.execute('''
            SELECT customer_id, username, contact, email 
            FROM customers
            ORDER BY customer_id
        ''').fetchall()
        
        return render_template('customer_orders.html', 
                            orders=orders,
                            order_items=order_items,
                            customers=customers)
    except Exception as e:
        print(f"Error loading billing data: {e}")
        flash('An error occurred while loading billing data', 'danger')
        return redirect(url_for('manager_dashboard'))
    finally:
        conn.close()


@app.route('/billing')
def billing():
    if 'user_id' not in session or session.get('role') not in ['manager', 'waiter']:
        flash('You do not have permission to view this page', 'danger')
        return redirect(url_for('login_home'))
    
    conn = get_db_connection()
    try:
        # Get orders with customer names and totals
        orders = conn.execute('''
            SELECT o.order_id, c.username as customer_name, 
                   o.order_date, SUM(mi.price * oi.quantity) as total_amount
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN menu_items mi ON oi.item_id = mi.item_id
            GROUP BY o.order_id
            ORDER BY o.order_date DESC
        ''').fetchall()
        
        # Get order items with names and calculated totals
        order_items = conn.execute('''
            SELECT oi.order_id, mi.name as item_name, 
                   oi.quantity, mi.price, 
                   (mi.price * oi.quantity) as item_total
            FROM order_items oi
            JOIN menu_items mi ON oi.item_id = mi.item_id
            ORDER BY oi.order_id
        ''').fetchall()
        
        # Get all customers (without passwords)
        customers = conn.execute('''
            SELECT customer_id, username, contact, email 
            FROM customers
            ORDER BY customer_id
        ''').fetchall()
        
        return render_template('billing.html', 
                            orders=orders,
                            order_items=order_items,
                            customers=customers)
    except Exception as e:
        print(f"Error loading billing data: {e}")
        flash('An error occurred while loading billing data', 'danger')
        return redirect(url_for('manager_dashboard'))
    finally:
        conn.close()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('new_registration.html')
    
    # Handle POST request (form submission)
    username = request.form.get('username')
    email = request.form.get('email')
    contact = request.form.get('contact')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    # Basic validation
    if not all([username, email, contact, password, confirm_password]):
        flash('All fields are required', 'danger')
        return redirect(url_for('register'))
    
    if password != confirm_password:
        flash('Passwords do not match', 'danger')
        return redirect(url_for('register'))
    
    conn = get_db_connection()
    try:
        # Check if email already exists
        existing_user = conn.execute(
            'SELECT 1 FROM customers WHERE email = ?', 
            (email,)
        ).fetchone()
        
        if existing_user:
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        # Insert new customer
        conn.execute(
            'INSERT INTO customers (username, email, contact, password) VALUES (?, ?, ?, ?)',
            (username, email, contact, password)
        )
        conn.commit()
        
        flash('Registration successful! Please login', 'success')
        return redirect(url_for('login'))
        
    except sqlite3.IntegrityError as e:
        conn.rollback()
        flash('Registration failed. Please try again.', 'danger')
        return redirect(url_for('register'))
    except Exception as e:
        conn.rollback()
        print(f"Error during registration: {e}")
        flash('An error occurred during registration', 'danger')
        return redirect(url_for('register'))
    finally:
        conn.close()


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)