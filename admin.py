from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash, session
from init_database import get_db_connection
from functools import wraps
import logging
from datetime import datetime, timedelta
import json

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
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('auth.login', next=request.url))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT is_admin FROM users WHERE id = %s", (session['user_id'],))
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

        # Revenue growth calculation
        current_month = datetime.now().replace(day=1)
        prev_month = (current_month - timedelta(days=1)).replace(day=1)
        
        cursor.execute("""
            SELECT COALESCE(SUM(total_price), 0) as revenue 
            FROM orders 
            WHERE status = 'completed' 
            AND order_date >= %s 
            AND order_date < %s
        """, (current_month, current_month + timedelta(days=32)))
        current_rev = cursor.fetchone()['revenue']
        
        cursor.execute("""
            SELECT COALESCE(SUM(total_price), 0) as revenue 
            FROM orders 
            WHERE status = 'completed' 
            AND order_date >= %s 
            AND order_date < %s
        """, (prev_month, current_month))
        prev_rev = cursor.fetchone()['revenue']
        
        revenue_growth = round(((current_rev - prev_rev) / prev_rev * 100) if prev_rev else 0, 1)

        cursor.execute("SELECT COUNT(*) as pending_orders FROM orders WHERE status = 'pending'")
        pending_orders = cursor.fetchone()['pending_orders']

        cursor.execute("SELECT COUNT(*) as declined_orders FROM orders WHERE status = 'declined'")
        declined_orders = cursor.fetchone()['declined_orders']

        # Get recent activity
        cursor.execute("""
            SELECT 
                o.order_id, o.order_code, o.status, o.order_date,
                o.customer_name, o.total_price, o.store_type,
                u.username as customer_username
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            ORDER BY o.order_date DESC
            LIMIT 10
        """)
        recent_activity = cursor.fetchall()

        metrics = {
            'total_users': total_users,
            'new_users': new_users,
            'total_orders': total_orders,
            'avg_order_value': avg_order_value,
            'total_revenue': total_revenue,
            'revenue_growth': revenue_growth,
            'pending_orders': pending_orders,
            'declined_orders': declined_orders,
            'current_month_revenue': current_rev,
            'previous_month_revenue': prev_rev
        }

        # Get users and orders
        cursor.execute("SELECT id, first_name, last_name, username, email, created_at, is_admin FROM users")
        users = cursor.fetchall()

        cursor.execute("""
            SELECT 
                o.*, 
                u.username as customer_name, 
                u.email,
                (SELECT COUNT(*) FROM order_items WHERE order_id = o.order_id) as item_count
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
                             recent_activity=recent_activity,
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
            decline_reason = request.form.get('decline_reason', '')

            # Validate status transition
            cursor.execute("SELECT status FROM orders WHERE order_id = %s", (order_id,))
            current_status = cursor.fetchone()['status']

            valid_transitions = {
                'pending': ['approved', 'declined'],
                'approved': ['processing', 'declined'],
                'processing': ['completed', 'cancelled'],
                'declined': [],
                'completed': [],
                'cancelled': []
            }

            if new_status not in valid_transitions.get(current_status, []):
                flash(f"Invalid status transition from {current_status} to {new_status}", "error")
                return redirect(url_for('admin.admin_order_detail', order_id=order_id))

            # Update order
            cursor.execute("""
                UPDATE orders 
                SET status = %s, 
                    admin_notes = %s,
                    decline_reason = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE order_id = %s
            """, (new_status, admin_notes, decline_reason if new_status == 'declined' else None, order_id))
            conn.commit()

            flash(f"Order status updated to {new_status} successfully!", "success")
            return redirect(url_for('admin.admin_order_detail', order_id=order_id))

        # Get order details
        cursor.execute("""
            SELECT 
                o.*, 
                u.username as customer_username, 
                u.email,
                (SELECT COUNT(*) FROM order_items WHERE order_id = o.order_id) as item_count
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

        # Get status history
        cursor.execute("""
            SELECT 
                status,
                updated_at as timestamp,
                CASE 
                    WHEN status = 'pending' THEN 'Order received'
                    WHEN status = 'approved' THEN 'Order approved'
                    WHEN status = 'processing' THEN 'Processing started'
                    WHEN status = 'completed' THEN 'Order completed'
                    WHEN status = 'declined' THEN 'Order declined'
                    WHEN status = 'cancelled' THEN 'Order cancelled'
                END as description
            FROM orders 
            WHERE order_id = %s
            ORDER BY updated_at
        """, (order_id,))
        status_history = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('admin/order_detail.html', 
                            order=order, 
                            items=items,
                            status_history=status_history)
    except Exception as e:
        logger.error(f"Error in admin order detail: {str(e)}")
        flash("An error occurred while processing the order.", "error")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/update-order-status', methods=['POST'])
@admin_required
def update_order_status():
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        new_status = data.get('status')
        admin_notes = data.get('admin_notes', '')
        decline_reason = data.get('decline_reason', '')

        if not order_id or not new_status:
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get current status
        cursor.execute("SELECT status FROM orders WHERE order_id = %s", (order_id,))
        current_status = cursor.fetchone()['status']

        # Validate status transition
        valid_transitions = {
            'pending': ['approved', 'declined'],
            'approved': ['processing', 'declined'],
            'processing': ['completed', 'cancelled'],
            'declined': [],
            'completed': [],
            'cancelled': []
        }

        if new_status not in valid_transitions.get(current_status, []):
            return jsonify({
                'success': False,
                'message': f'Invalid status transition from {current_status} to {new_status}'
            }), 400

        # Update order
        cursor.execute("""
            UPDATE orders 
            SET status = %s, 
                admin_notes = %s,
                decline_reason = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_id = %s
        """, (new_status, admin_notes, decline_reason if new_status == 'declined' else None, order_id))
        conn.commit()

        # Get updated order for response
        cursor.execute("""
            SELECT 
                o.*,
                u.username as customer_username
            FROM orders o
            LEFT JOIN users u ON o.user_id = u.id
            WHERE o.order_id = %s
        """, (order_id,))
        updated_order = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Order status updated successfully',
            'order': updated_order
        })

    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred'}), 500

@admin_bp.route('/user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_user_detail(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            is_admin = request.form.get('is_admin') == 'on'
            
            cursor.execute("""
                UPDATE users 
                SET is_admin = %s
                WHERE id = %s
            """, (is_admin, user_id))
            conn.commit()
            
            flash("User updated successfully!", "success")
            return redirect(url_for('admin.admin_user_detail', user_id=user_id))

        # Get user details
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            flash("User not found.", "error")
            return redirect(url_for('admin.admin_dashboard'))

        # Get user orders
        cursor.execute("""
            SELECT 
                o.order_id, o.order_code, o.status, 
                o.order_date, o.total_price, o.store_type
            FROM orders o
            WHERE o.user_id = %s
            ORDER BY o.order_date DESC
            LIMIT 10
        """, (user_id,))
        orders = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('admin/user_detail.html', 
                            user=user, 
                            orders=orders)
    except Exception as e:
        logger.error(f"Error in admin user detail: {str(e)}")
        flash("An error occurred while processing the user.", "error")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/analytics')
@admin_required
def admin_analytics():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Revenue by month for the last 6 months
        cursor.execute("""
            SELECT 
                DATE_FORMAT(order_date, '%Y-%m') as month,
                SUM(total_price) as revenue,
                COUNT(*) as order_count
            FROM orders
            WHERE status = 'completed'
            AND order_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(order_date, '%Y-%m')
            ORDER BY month
        """)
        revenue_data = cursor.fetchall()

        # Orders by status
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM orders
            GROUP BY status
        """)
        status_data = cursor.fetchall()

        # Revenue by store type
        cursor.execute("""
            SELECT 
                store_type,
                SUM(total_price) as revenue,
                COUNT(*) as order_count
            FROM orders
            WHERE status = 'completed'
            GROUP BY store_type
        """)
        store_data = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('admin/analytics.html',
                            revenue_data=revenue_data,
                            status_data=status_data,
                            store_data=store_data)
    except Exception as e:
        logger.error(f"Error in admin analytics: {str(e)}")
        flash("An error occurred while loading analytics.", "error")
        return redirect(url_for('admin.admin_dashboard'))