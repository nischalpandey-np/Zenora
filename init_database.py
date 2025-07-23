import mysql.connector
import os
from dotenv import load_dotenv
import logging
from werkzeug.security import generate_password_hash
from typing import Optional, Dict, Any, Union
import time

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'digibistro'),
    'port': 3306,
    'auth_plugin': 'mysql_native_password',
    'connect_timeout': 5
}

# -------------------------------------------------
# Step 1: Ensure database exists
# -------------------------------------------------
def create_database_if_not_exists():
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port']
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        cursor.close()
        conn.close()
        logger.info(f"Database '{DB_CONFIG['database']}' ensured.")
    except mysql.connector.Error as err:
        logger.error(f"Error creating database: {err}")
        raise

# -------------------------------------------------
# Step 2: Get DB connection
# -------------------------------------------------
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

# -------------------------------------------------
# Step 3: Create tables
# -------------------------------------------------
def create_tables():
    create_database_if_not_exists()

    table_definitions = [
        """CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE
        )""",
       """CREATE TABLE IF NOT EXISTS orders (
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
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
)""",
        """CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            item_name VARCHAR(50) NOT NULL,
            quantity INT NOT NULL,
            item_total DECIMAL(10,2) NOT NULL,
            notes TEXT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
        )""", 
        """CREATE TABLE IF NOT EXISTS reviews (
            review_id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            user_id INT NOT NULL,
            rating INT NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )"""
    ]

    conn = get_db_connection()
    cursor = conn.cursor()
    for table_sql in table_definitions:
        cursor.execute(table_sql)
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("All tables created successfully.")

# -------------------------------------------------
# Step 4: Save user
# -------------------------------------------------
def save_user(first_name: str, last_name: str, username: str, email: str, password: str) -> Optional[int]:
    password_hash = generate_password_hash(password)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO users (first_name, last_name, username, email, password_hash)
                          VALUES (%s, %s, %s, %s, %s)''',
                       (first_name, last_name, username, email, password_hash))
        user_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"User created with ID: {user_id}")
        return user_id
    except mysql.connector.IntegrityError as e:
        logger.warning(f"User already exists: {e}")
        return None
    except Exception as e:
        logger.error(f"Error saving user: {e}")
        return None

# -------------------------------------------------
# Step 5: Get user
# -------------------------------------------------
def get_user(username: str) -> Optional[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Error retrieving user: {e}")
        return None

# -------------------------------------------------
# Step 6: Save order
# -------------------------------------------------
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
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.start_transaction()

        cursor.execute('''INSERT INTO orders
                          (customer_name, phone_number, customer_address, total_price,
                           user_id, payment_method, order_code, delivery_fee, status, store_type)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                       (customer_name, phone_number, customer_address, total_price,
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

        cursor.executemany('''INSERT INTO order_items
                              (order_id, item_name, quantity, item_total)
                              VALUES (%s, %s, %s, %s)''', items)

        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Order {order_id} saved successfully.")
        return order_id
    except Exception as e:
        logger.error(f"Error saving order: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn and conn.is_connected():
            conn.close()

# -------------------------------------------------
# Bootstrap when run directly
# -------------------------------------------------
if __name__ == '__main__':
    create_tables()
