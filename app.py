"""
Main application file for the E-commerce platform with restaurant and clothing stores.
Handles user authentication, menu display, order processing, and profile management.
"""

from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from functools import wraps
from dotenv import load_dotenv
import random
import string
import json
import os
from datetime import datetime

# Custom modules for DB and route management
from init_database import save_order_to_db, get_db_connection, create_tables
from auth import auth_bp
from admin import admin_bp

# Load environment variables from .env file
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

# Register modular Blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')

# Determine if the app is running on PythonAnywhere
IS_PYTHONANYWHERE = 'PYTHONANYWHERE_DOMAIN' in os.environ

# Static price list for restaurant and clothing items
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

# -------------------------
# Utility Functions
# -------------------------

def format_currency(value):
    """Format a float value into Nepali Rupees string."""
    return f"Nrs: {value:,.2f}"

@app.template_filter('format_currency')
def format_currency_filter(value):
    """Template filter for currency formatting."""
    return format_currency(value)

def generate_order_code():
    """Generate a random 6-character alphanumeric order code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def validate_phone_number(phone):
    """Validate Nepali phone number format."""
    if len(phone) != 10 or not phone.startswith(('98', '97', '96')):
        return False
    return phone.isdigit()

# -------------------------
# Authentication Decorator
# -------------------------

def login_required(f):
    """Decorator to ensure user is logged in."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return wrapper

# -------------------------
# Context Processors
# -------------------------

@app.context_processor
def inject_user():
    """Inject logged-in user data into all templates."""
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
    """Inject cart item count into templates."""
    cart_count = 0
    if 'items' in session:
        try:
            items = json.loads(session['items'])
            cart_count = sum(items.values())
        except json.JSONDecodeError:
            session.pop('items', None)
    return {'cart_count': cart_count}

# -------------------------
# Public Routes
# -------------------------

@app.route('/')
@app.route('/index.html')
def index():
    """Render the home page."""
    return render_template('index.html')

# -------------------------
# Restaurant Menu
# -------------------------

@app.route('/digibistro')
def digibistro():
    """Render the digital bistro landing page."""
    return render_template('gourmetbistro/digibistro.html', menu_items=ITEM_PRICES)

@app.route('/restaurant/menu', methods=['GET', 'POST'])
@login_required
def view_menu():
    """Handle restaurant menu viewing and item selection."""
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

# -------------------------
# Clothing Menu
# -------------------------

@app.route('/clothstore')
def clothstore():
    """Render the clothing store landing page."""
    return render_template('cloth/clothstore.html', clothing_items=CLOTHING_PRICES)

@app.route('/clothing/menu', methods=['GET', 'POST'])
@login_required
def view_clothing():
    """Handle clothing menu viewing and item selection."""
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

# -------------------------
# Payment & Order Details
# -------------------------

@app.route('/select-payment', methods=['GET', 'POST'])
@login_required
def select_payment():
    """Handle payment method selection."""
    if 'items' not in session:
        flash("Your cart is empty. Please add items first.", "error")
        return redirect(url_for('index'))

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

    try:
        items = json.loads(session['items'])
    except json.JSONDecodeError:
        session.pop('items', None)
        flash("Invalid cart data. Please try again.", "error")
        return redirect(url_for('index'))

    store_type = session.get('store_type', 'restaurant')
    price_list = CLOTHING_PRICES if store_type == 'clothing' else ITEM_PRICES

    subtotal = sum(price_list[item] * qty for item, qty in items.items())

    return render_template('ordering/order_payment.html',
                         items=items,
                         subtotal=subtotal,
                         delivery_fee=DELIVERY_FEE,
                         item_prices=price_list,
                         store_type=store_type)

@app.route('/order-details', methods=['GET', 'POST'])
@login_required
def order_details():
    """Handle order details submission and order confirmation."""
    if 'items' not in session or 'payment_method' not in session:
        flash("Please complete your order process from the beginning.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        required = ['customer-name', 'phone-number', 'customer-address']
        if not all(field in request.form for field in required):
            flash("Please fill in all required fields.", "error")
            return redirect(url_for('order_details'))

        customer_name = request.form['customer-name'].strip()
        phone_number = request.form['phone-number'].strip()
        customer_address = request.form['customer-address'].strip()
        house_no = request.form.get('house-no', '').strip()

        # Validate phone number
        if not validate_phone_number(phone_number):
            flash("Please enter a valid Nepali phone number (98/97/96XXXXXXXX).", "error")
            return redirect(url_for('order_details'))

        try:
            items = json.loads(session['items'])
        except json.JSONDecodeError:
            session.pop('items', None)
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

        # Clear session data
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

# -------------------------
# User Profile
# -------------------------

@app.route('/profile')
@login_required
def user_profile():
    """Display user profile with order history."""
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

@app.route('/order/<int:order_id>/received', methods=['POST'])
@login_required
def mark_order_received(order_id):
    """Mark an order as received by the user."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verify the order belongs to the user
    cursor.execute("SELECT user_id FROM orders WHERE order_id = %s", (order_id,))
    order = cursor.fetchone()
    
    if not order or order['user_id'] != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    cursor.execute("""
        UPDATE orders 
        SET received_status = 'received'
        WHERE order_id = %s
    """, (order_id,))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/order/<int:order_id>/not-received', methods=['POST'])
@login_required
def mark_order_not_received(order_id):
    """Mark an order as not received by the user."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verify the order belongs to the user
    cursor.execute("SELECT user_id FROM orders WHERE order_id = %s", (order_id,))
    order = cursor.fetchone()
    
    if not order or order['user_id'] != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    cursor.execute("""
        UPDATE orders 
        SET received_status = 'not_received',
            status = 'cancelled'
        WHERE order_id = %s
    """, (order_id,))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/order/<int:order_id>/review', methods=['POST'])
@login_required
def submit_review(order_id):
    """Submit a review for a received order."""
    data = request.get_json()
    rating = data.get('rating')
    review = data.get('review')
    
    if not rating or not review:
        return jsonify({'error': 'Rating and review are required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verify the order belongs to the user and was received
    cursor.execute("""
        SELECT user_id, received_status 
        FROM orders 
        WHERE order_id = %s
    """, (order_id,))
    order = cursor.fetchone()
    
    if not order or order['user_id'] != session['user_id'] or order['received_status'] != 'received':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Store the review in the database
    cursor.execute("""
        INSERT INTO reviews (order_id, user_id, rating, comment)
        VALUES (%s, %s, %s, %s)
    """, (order_id, session['user_id'], rating, review))
    conn.commit()
    
    cursor.close()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/profile/order/<int:order_id>')
@login_required
def user_order_detail(order_id):
    """Display detailed information for a specific order."""
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

# -------------------------
# Error Handlers
# -------------------------

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors."""
    return render_template('errors/500.html'), 500

# -------------------------
# App Runner
# -------------------------

if __name__ == '__main__':
    create_tables()
    if IS_PYTHONANYWHERE:
        app.run()
    else:
        app.run(host='0.0.0.0', port=5000, debug=True)