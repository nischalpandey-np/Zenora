# Updated admin.py with metrics calculation
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from init_database import get_db_connection
from functools import wraps
import logging

admin_bp = Blueprint('admin', __name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login', next=request.url))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user or not user.get('is_admin'):
            flash("You don't have permission to access this page.", "error")
            return redirect(url_for('index'))
            
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@admin_required
def admin_dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Calculate metrics
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cursor.fetchone()['total_users']
        
        cursor.execute("SELECT COUNT(*) as new_users FROM users WHERE created_at >= CURDATE() - INTERVAL 7 DAY")
        new_users = cursor.fetchone()['new_users']
        
        cursor.execute("SELECT COUNT(*) as total_orders FROM orders")
        total_orders = cursor.fetchone()['total_orders']
        
        cursor.execute("SELECT AVG(total_price) as avg_order_value FROM orders")
        avg_order_value = cursor.fetchone()['avg_order_value'] or 0
        
        cursor.execute("SELECT SUM(total_price) as total_revenue FROM orders WHERE status = 'completed'")
        total_revenue = cursor.fetchone()['total_revenue'] or 0
        
        # Fixed revenue growth calculation
        cursor.execute("""
            SELECT 
                (COALESCE(SUM(CASE WHEN order_date >= CURDATE() - INTERVAL 1 MONTH AND order_date < CURDATE() THEN total_price END), 0) -
                COALESCE(SUM(CASE WHEN order_date >= CURDATE() - INTERVAL 2 MONTH AND order_date < CURDATE() - INTERVAL 1 MONTH THEN total_price END), 0)
            ) / 
            NULLIF(SUM(CASE WHEN order_date >= CURDATE() - INTERVAL 2 MONTH AND order_date < CURDATE() - INTERVAL 1 MONTH THEN total_price END), 0) * 100 
            AS revenue_growth 
            FROM orders
            WHERE status = 'completed'
        """)
        growth_result = cursor.fetchone()['revenue_growth']
        revenue_growth = round(growth_result if growth_result else 0, 1)
        
        cursor.execute("SELECT COUNT(*) as pending_orders FROM orders WHERE status = 'pending'")
        pending_orders = cursor.fetchone()['pending_orders']
        
        cursor.execute("SELECT COUNT(*) as declined_orders FROM orders WHERE status = 'declined'")
        declined_orders = cursor.fetchone()['declined_orders']
        
        metrics = {
            'total_users': total_users,
            'new_users': new_users,
            'total_orders': total_orders,
            'avg_order_value': avg_order_value,
            'total_revenue': total_revenue,
            'revenue_growth': revenue_growth,
            'pending_orders': pending_orders,
            'declined_orders': declined_orders
        }
        
        # Get users and orders
        cursor.execute("SELECT id, first_name, last_name, username, email, created_at FROM users")
        users = cursor.fetchall()
        
        cursor.execute("""
            SELECT o.*, u.username, u.email 
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            ORDER BY o.order_date DESC
            LIMIT 50
        """)
        orders = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('admin/dashboard.html', 
                             users=users, 
                             orders=orders,
                             metrics=metrics,
                             store_types=['restaurant', 'clothing'])
    except Exception as e:
        logger.error(f"Error in admin dashboard: {str(e)}")
        flash("An error occurred while loading the admin dashboard.", "error")
        return redirect(url_for('index'))

@admin_bp.route('/order/<int:order_id>', methods=['GET', 'POST'])
@admin_required
def admin_order_detail(order_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            new_status = request.form.get('status')
            admin_notes = request.form.get('admin_notes', '')
            
            if new_status not in ['pending', 'processing', 'completed', 'cancelled']:
                flash("Invalid status selected.", "error")
                return redirect(url_for('admin.admin_order_detail', order_id=order_id))
            
            cursor.execute("""
                UPDATE orders 
                SET status = %s, admin_notes = %s 
                WHERE order_id = %s
            """, (new_status, admin_notes, order_id))
            conn.commit()
            
            flash("Order status updated successfully!", "success")
            return redirect(url_for('admin.admin_order_detail', order_id=order_id))
        
        cursor.execute("""
            SELECT o.*, u.username, u.email 
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            WHERE o.order_id = %s
        """, (order_id,))
        order = cursor.fetchone()
        
        if not order:
            flash("Order not found.", "error")
            return redirect(url_for('admin.admin_dashboard'))
        
        cursor.execute("SELECT * FROM order_items WHERE order_id = %s", (order_id,))
        items = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('admin/order_detail.html', order=order, items=items)
    except Exception as e:
        logger.error(f"Error in admin order detail: {str(e)}")
        flash("An error occurred while processing the order.", "error")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/order/update', methods=['POST'])
@admin_required
def admin_update_order():
    try:
        order_id = request.form.get('order_id')
        new_status = request.form.get('status')
        decline_reason = request.form.get('decline_reason', '')
        admin_notes = request.form.get('admin_notes', '')
        
        if not order_id:
            flash("Order ID is missing", "error")
            return redirect(url_for('admin.admin_dashboard'))
            
        try:
            order_id = int(order_id)
        except ValueError:
            flash("Invalid Order ID", "error")
            return redirect(url_for('admin.admin_dashboard'))
            
        if new_status not in ['pending', 'approved', 'declined', 'processing', 'completed']:
            flash("Invalid status selected.", "error")
            return redirect(url_for('admin.admin_dashboard'))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            UPDATE orders 
            SET status = %s, 
                decline_reason = %s,
                admin_notes = %s
            WHERE order_id = %s
        """, (new_status, decline_reason if new_status == 'declined' else None, admin_notes, order_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Fixed: Replace add_toast with flash
        flash(f"Order status updated to {new_status}.", "success")
        return redirect(url_for('admin.admin_order_detail', order_id=order_id))
        
    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}")
        flash("An error occurred while updating the order.", "error")
        return redirect(url_for('admin.admin_dashboard'))