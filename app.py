from flask import Flask, render_template, redirect, url_for, flash, request, session
from functools import wraps
from dotenv import load_dotenv
import random
import string
import json
import os

from init_database import save_order_to_db, get_db_connection, create_tables
from auth import auth_bp
from admin import admin_bp

# Load environment variables
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')



# Check if running on PythonAnywhere
IS_PYTHONANYWHERE = 'PYTHONANYWHERE_DOMAIN' in os.environ

# Price Lists
ITEM_PRICES = {
    "Pasta": 120.00, "Chi-Momo": 160.00, "Burger": 220.00,
    "Coffee": 120.00, "Tea": 30.00, "Chowmein": 180.00,
    "Samosa": 35.00, "Keema Noodles": 190.00, "Laphing": 120.00,
    "Corn Dog": 220.00, "Sauces": 330.00, "Momo": 150.00
}

CLOTHING_PRICES = {
    "T-Shirt": 800.00, "Jeans": 1500.00, "Dress": 2000.00,
    "Jacket": 2500.00, "Sneakers": 3000.00, "Cap": 400.00,
    "Hoodie": 1800.00, "Shorts": 600.00, "Skirt": 1200.00,
    "Shirt": 1000.00, "Scarf": 300.00, "Belt": 500.00
}

DELIVERY_FEE = 10.00




# -----------------------
# Utility Functions
# -----------------------

def format_currency(value):
    return f"Nrs: {value:,.2f}"

@app.template_filter('format_currency')
def format_currency_filter(value):
    return format_currency(value)

def generate_order_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# -----------------------
# Decorators
# -----------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return wrapper

# -----------------------
# Context Processors
# -----------------------

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
    return {'user': user}

@app.context_processor
def inject_cart_count():
    cart_count = 0
    if 'items' in session:
        items = json.loads(session['items'])
        cart_count = sum(items.values())
    return {'cart_count': cart_count}

# -----------------------
# Routes
# -----------------------

@app.route('/')
@app.route('/index.html')
def index():
    return render_template('index.html')

# @app.route('/contact')
# def contact():
#     return render_template('contact.html')

# @app.route('/about')
# def about():
#     return render_template('about.html')


# --- Restaurant Routes ---

@app.route('/digibistro')
def digibistro():
    return render_template('gourmetbistro/digibistro.html', menu_items=ITEM_PRICES)

@app.route('/restaurant/menu', methods=['GET', 'POST'])
@login_required
def view_menu():
    if request.method == 'POST':
        items = {
            item: int(request.form.get(item, 0))
            for item in ITEM_PRICES if int(request.form.get(item, 0)) > 0
        }

        if not items:
            flash("Please select at least one item!", "error")
            return redirect(url_for('view_menu'))

        session['items'] = json.dumps(items)
        session['store_type'] = 'restaurant'
        return redirect(url_for('select_payment'))

    return render_template('gourmetbistro/viewMenu.html', menu_items=ITEM_PRICES)

# --- Clothing Routes ---

@app.route('/clothstore')
def clothstore():
    return render_template('cloth/clothstore.html', clothing_items=CLOTHING_PRICES)

@app.route('/clothing/menu', methods=['GET', 'POST'])
@login_required
def view_clothing():
    if request.method == 'POST':
        items = {
            item: int(request.form.get(item, 0))
            for item in CLOTHING_PRICES if int(request.form.get(item, 0)) > 0
        }

        if not items:
            flash("Please select at least one item!", "error")
            return redirect(url_for('view_clothing'))

        session['items'] = json.dumps(items)
        session['store_type'] = 'clothing'
        return redirect(url_for('select_payment'))

    return render_template('cloth/viewClothing.html', clothing_items=CLOTHING_PRICES)

# --- Shared Ordering Routes ---

@app.route('/select-payment', methods=['GET', 'POST'])
@login_required
def select_payment():
    if request.method == 'POST':
        method = request.form.get('payment_method')
        if method not in ['card', 'cash_on_delivery']:
            flash("Invalid payment method selected.", "error")
            return redirect(url_for('select_payment'))
        
        if method == 'card':
            flash("Online payment is not available. Please use Cash on Delivery.", "error")
            return redirect(url_for('select_payment'))

        session['payment_method'] = method
        return redirect(url_for('order_details'))

    items = json.loads(session.get('items', '{}'))
    store_type = session.get('store_type', 'restaurant')
    price_list = CLOTHING_PRICES if store_type == 'clothing' else ITEM_PRICES

    if not items:
        flash("Please select items first.", "error")
        return redirect(url_for('index'))

    subtotal = sum(price_list[item] * qty for item, qty in items.items())

    return render_template('ordering/order_payment.html',
                           items=items,
                           subtotal=subtotal,
                           delivery_fee=DELIVERY_FEE,
                           item_prices=price_list,
                           store_type=store_type,
                           ITEM_PRICES=ITEM_PRICES,
                           CLOTHING_PRICES=CLOTHING_PRICES)

@app.route('/order-details', methods=['GET', 'POST'])
@login_required
def order_details():
    if request.method == 'POST':
        required = ['customer-name', 'phone-number', 'customer-address']
        if not all(field in request.form for field in required):
            flash("Please fill in all required fields.", "error")
            return redirect(url_for('order_details'))

        customer_name = request.form['customer-name'].strip()
        phone_number = request.form['phone-number'].strip()
        customer_address = request.form['customer-address'].strip()
        house_no = request.form.get('house-no', '').strip()

        try:
            items = json.loads(session['items'])
        except Exception:
            flash("Invalid order data.", "error")
            return redirect(url_for('index'))

        store_type = session.get('store_type', 'restaurant')
        price_list = CLOTHING_PRICES if store_type == 'clothing' else ITEM_PRICES
        subtotal = sum(price_list.get(item, 0) * qty for item, qty in items.items())
        delivery_fee = DELIVERY_FEE if session.get('payment_method') == 'cash_on_delivery' else 0
        total_price = subtotal + delivery_fee

        order_details = {
            item: {'quantity': qty, 'item_total': price_list.get(item, 0) * qty}
            for item, qty in items.items()
        }

        order_code = generate_order_code()
        user_id = session.get('user_id')

        order_id = save_order_to_db(
            customer_name=customer_name,
            phone_number=phone_number,
            customer_address=customer_address,
            order_details=order_details,
            total_price=total_price,
            user_id=user_id,
            payment_method=session.get('payment_method', 'cash_on_delivery'),
            order_code=order_code,
            delivery_fee=delivery_fee,
            store_type=store_type
        )

        if not order_id:
            flash("Order failed. Please try again.", "error")
            return redirect(url_for('index'))

        # Clear cart after successful order
        session.pop('items', None)
        session.pop('payment_method', None)
        session.pop('store_type', None)

        return render_template('ordering/order_summary.html',
                               customer_name=customer_name,
                               customer_address=customer_address,
                               house_no=house_no or 'N/A',
                               phone_number=phone_number,
                               order_details=order_details,
                               subtotal=subtotal,
                               total_price=total_price,
                               payment_method='Cash on Delivery',
                               order_code=order_code,
                               delivery_fee=delivery_fee,
                               store_type=store_type)

    return render_template('ordering/order.html')

# --- User Profile ---

@app.route('/profile')
@login_required
def user_profile():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    cursor.execute("""
        SELECT * FROM orders 
        WHERE user_id = %s 
        ORDER BY order_date DESC
        LIMIT 10
    """, (user_id,))
    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('auth/profile.html', user=user, orders=orders)

@app.route('/profile/order/<int:order_id>')
@login_required
def user_order_detail(order_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.*, 
               GROUP_CONCAT(oi.item_name SEPARATOR ', ') as items,
               SUM(oi.quantity) as total_items
        FROM orders o
        LEFT JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_id = %s AND o.user_id = %s
        GROUP BY o.order_id
    """, (order_id, user_id))
    order = cursor.fetchone()

    if not order:
        flash("Order not found.", "error")
        return redirect(url_for('user_profile'))

    cursor.execute("SELECT * FROM order_items WHERE order_id = %s", (order_id,))
    items = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('ordering/order_detail.html', order=order, items=items)

# --- Error Pages ---

# @app.errorhandler(404)
# def page_not_found(e):
#     return render_template('404.html'), 404

# @app.errorhandler(500)
# def internal_server_error(e):
#     return render_template('500.html'), 500

# -----------------------
# Run the App
# -----------------------

if __name__ == '__main__':
    create_tables()
    if IS_PYTHONANYWHERE:
        app.run()
    else:
        app.run(host='0.0.0.0', port=5000, debug=True)
