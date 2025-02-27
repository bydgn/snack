from flask import Flask, render_template, request, jsonify
import mysql.connector
import json
import sys

app = Flask(__name__)

def get_db_connection():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="rs1374280_snack",
            password="12112027Bd--",
            database="rs1374280_snack"
        )
    except mysql.connector.Error as e:
        print(f"Veritabanı hatası: {e}")
        raise

cart = []

@app.route('/')
def index():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM categories WHERE status = 1 ORDER BY order_number")
        categories = cursor.fetchall()
        
        cursor.execute("SELECT * FROM menu_items WHERE status = 1 ORDER BY order_number")
        menu_items = cursor.fetchall()
        
        conn.close()
        return render_template('index.html', categories=categories, menu_items=menu_items)
    except Exception as e:
        app.logger.error(f"Index hatası: {e}")
        return "Bir hata oluştu", 500

@app.route('/order_modal/<int:item_id>')
def order_modal(item_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM menu_items WHERE id = %s AND status = 1", (item_id,))
        item = cursor.fetchone()
        if not item:
            conn.close()
            return "Ürün bulunamadı", 404
        
        cursor.execute("SELECT ingredients_status, sauces_status, meat_types_status FROM categories WHERE id = %s", (item['category_id'],))
        category = cursor.fetchone()
        
        ingredients = []
        if category['ingredients_status']:
            cursor.execute("""
                SELECT i.*
                FROM ingredients i
                JOIN menu_item_ingredients mi ON i.id = mi.ingredient_id
                WHERE mi.menu_item_id = %s AND i.status = 1
                ORDER BY i.order_number
            """, (item_id,))
            ingredients = cursor.fetchall()
        
        sauces = []
        if category['sauces_status']:
            cursor.execute("""
                SELECT s.*
                FROM sauces s
                JOIN menu_item_sauces ms ON s.id = ms.sauce_id
                WHERE ms.menu_item_id = %s AND s.status = 1
                ORDER BY s.order_number
            """, (item_id,))
            sauces = cursor.fetchall()
        
        meat_types = []
        if category['meat_types_status']:
            cursor.execute("""
                SELECT mt.*
                FROM meat_types mt
                JOIN menu_item_meat_types mmt ON mt.id = mmt.meat_type_id
                WHERE mmt.menu_item_id = %s AND mt.status = 1
                ORDER BY mt.order_number
            """, (item_id,))
            meat_types = cursor.fetchall()
        
        conn.close()
        return render_template('order_modal.html', item=item, sauces=sauces, ingredients=ingredients, meat_types=meat_types)
    except Exception as e:
        app.logger.error(f"Order modal hatası: {e}")
        return "Bir hata oluştu", 500

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    try:
        item_id = int(request.form['item_id'])
        quantity = int(request.form['quantity'])
        selected_sauces = request.form.getlist('sauces')
        selected_ingredients = request.form.getlist('ingredients')
        selected_meat = request.form.get('meat_type')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM menu_items WHERE id = %s AND status = 1", (item_id,))
        item = cursor.fetchone()
        conn.close()
        
        if item:
            cart_item = {
                "item": item,
                "quantity": quantity,
                "sauces": selected_sauces,
                "ingredients": selected_ingredients,
                "meat_type": selected_meat
            }
            cart.append(cart_item)
            return jsonify({"message": "Ürün sepete eklendi", "cart_size": len(cart)})
        return jsonify({"message": "Hata oluştu"}), 400
    except Exception as e:
        app.logger.error(f"Add to cart hatası: {e}")
        return jsonify({"message": "Hata oluştu"}), 500

@app.route('/cart')
def cart_page():
    try:
        total = sum(item['item']['baseprice'] * item['quantity'] for item in cart)
        return render_template('cart_modal.html', cart=cart, total=total)
    except Exception as e:
        app.logger.error(f"Cart hatası: {e}")
        return "Bir hata oluştu", 500

@app.route('/submit_order', methods=['POST'])
def submit_order():
    try:
        if not cart:
            return jsonify({"message": "Sepet boş"}), 400
        
        masa_adi = request.form.get('table_name', 'Masa 1')
        total_amount = sum(item['item']['baseprice'] * item['quantity'] for item in cart)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO orders (table_number, status, total_amount) VALUES (%s, 'new', %s)",
                       (masa_adi, total_amount))
        order_id = cursor.lastrowid
        
        for item in cart:
            total_price = item['item']['baseprice'] * item['quantity']
            cursor.execute("""
                INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price, total_price, selected_meat_type, selected_sauces, selected_ingredients)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (order_id, item['item']['id'], item['quantity'], item['item']['baseprice'], total_price,
                  item['meat_type'], json.dumps(item['sauces']), json.dumps(item['ingredients'])))
            order_item_id = cursor.lastrowid
            
            if item['sauces']:
                for sauce in item['sauces']:
                    cursor.execute("INSERT INTO order_item_sauces (order_item_id, sauce_id) VALUES (%s, %s)",
                                   (order_item_id, sauce))
            if item['ingredients']:
                for ingredient in item['ingredients']:
                    cursor.execute("INSERT INTO order_item_ingredients (order_item_id, ingredient_id) VALUES (%s, %s)",
                                   (order_item_id, ingredient))
            if item['meat_type']:
                cursor.execute("INSERT INTO order_item_meat_types (order_item_id, meat_type_id) VALUES (%s, %s)",
                               (order_item_id, item['meat_type']))
        
        conn.commit()
        conn.close()
        cart.clear()
        return jsonify({"message": "Sipariş gönderildi"})
    except Exception as e:
        app.logger.error(f"Submit order hatası: {e}")
        return jsonify({"message": "Hata oluştu"}), 500

if __name__ == '__main__':
    # Port parametresini komut satırından al
    port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--port' else 8080
    app.run(host='0.0.0.0', port=port, debug=True)