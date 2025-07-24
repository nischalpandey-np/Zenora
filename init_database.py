import os
os.environ["MYSQLC_CONNECTOR_PURE"] = "True"
import mysql.connector

import time
import logging
from typing import Optional, Dict, Any, Union
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Load environment variables
load_dotenv()

# --------------------------------------
# Logging Configuration
# --------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False

# --------------------------------------
# Database Configuration for PythonAnywhere
# --------------------------------------
# DB_CONFIG = {
#     'host': 'zenora.mysql.pythonanywhere-services.com',
#     'user': 'zenora',
#     'password': 'nischal@__',
#     'database': 'zenora$digibistro',
#     'port': 3306,
#     'connect_timeout': 5
# }



DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'connect_timeout': int(os.getenv('DB_TIMEOUT', 5))
}

# --------------------------------------
# Get DB Connection
# --------------------------------------
def get_db_connection():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            logger.info("Database connection established.")
            return conn
        except mysql.connector.Error as err:
            logger.error(f"Connection attempt {attempt + 1} failed: {err}")
            time.sleep(1)
    raise Exception("Database connection failed after retries.")

# --------------------------------------
# Create Tables (Run manually only)
# --------------------------------------
def create_tables():
    table_definitions = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE,
            INDEX idx_username (username),
            INDEX idx_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(100) NOT NULL,
            phone_number VARCHAR(15) NOT NULL,
            customer_address TEXT NOT NULL,
            total_price DECIMAL(10,2) NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INT NULL,
            payment_method VARCHAR(20) NOT NULL,
            order_code VARCHAR(10) UNIQUE,
            delivery_fee DECIMAL(10,2) DEFAULT 0,
            status ENUM('pending', 'processing', 'completed', 'cancelled', 'approved', 'declined') DEFAULT 'pending',
            admin_notes TEXT NULL,
            decline_reason TEXT NULL,
            store_type ENUM('clothing', 'restaurant') DEFAULT 'restaurant',
            received_status ENUM('pending', 'received', 'not_received') DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            INDEX idx_order_date (order_date),
            INDEX idx_status (status),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            item_name VARCHAR(50) NOT NULL,
            quantity INT NOT NULL,
            item_total DECIMAL(10,2) NOT NULL,
            notes TEXT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
            INDEX idx_order_id (order_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """,
        """
        CREATE TABLE IF NOT EXISTS reviews (
            review_id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            user_id INT NOT NULL,
            rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_order_id (order_id),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    ]

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        for table_sql in table_definitions:
            try:
                cursor.execute(table_sql)
                logger.info("Table created successfully.")
            except mysql.connector.Error as err:
                logger.error(f"Error creating table: {err}")
                raise
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.commit()

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
    logger.info("All tables created successfully.")

# --------------------------------------
# Save User
# --------------------------------------
def save_user(first_name: str, last_name: str, username: str, email: str, password: str) -> Optional[int]:
    password_hash = generate_password_hash(password)
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (first_name, last_name, username, email, password_hash)
            VALUES (%s, %s, %s, %s, %s)
        ''', (first_name, last_name, username, email, password_hash))
        conn.commit()
        user_id = cursor.lastrowid
        logger.info(f"User created with ID: {user_id}")
        return user_id
    except mysql.connector.IntegrityError as e:
        logger.warning(f"User already exists: {e}")
        return None
    except Exception as e:
        logger.error(f"Error saving user: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --------------------------------------
# Get User by Username
# --------------------------------------
def get_user(username: str) -> Optional[Dict[str, Any]]:
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        return user
    except Exception as e:
        logger.error(f"Error retrieving user: {e}")
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --------------------------------------
# Save Order
# --------------------------------------
def save_order_to_db(
    customer_name: str,
    phone_number: str,
    customer_address: str,
    order_details: Dict[str, Dict[str, Union[int, float]]],
    total_price: float,
    user_id: Optional[int] = None,
    payment_method: str = 'cash_on_delivery',
    order_code: Optional[str] = None,
    delivery_fee: float = 0,
    status: str = 'pending',
    store_type: str = 'restaurant'
) -> Optional[int]:
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        cursor.execute('''
            INSERT INTO orders
            (customer_name, phone_number, customer_address, total_price,
             user_id, payment_method, order_code, delivery_fee, status, store_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (customer_name, phone_number, customer_address, total_price,
              user_id, payment_method, order_code, delivery_fee, status, store_type))

        order_id = cursor.lastrowid

        items = []
        for item, details in order_details.items():
            quantity = details.get('quantity', 0)
            item_total = details.get('item_total', 0)
            if quantity > 0:
                items.append((order_id, item, quantity, item_total))

        if not items:
            raise ValueError("No valid items in the order.")

        cursor.executemany('''
            INSERT INTO order_items (order_id, item_name, quantity, item_total)
            VALUES (%s, %s, %s, %s)
        ''', items)

        conn.commit()
        logger.info(f"Order {order_id} saved successfully.")
        return order_id
    except Exception as e:
        logger.error(f"Error saving order: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
