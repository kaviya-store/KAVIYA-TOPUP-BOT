import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# MongoDB Connection
MONGODB_URI = os.getenv("MONGODB_URI")

class Database:
    def __init__(self):
        try:
            self.client = MongoClient(MONGODB_URI)
            self.db = self.client["kaviya_topup_bot"]
            
            # Create collections
            self.users = self.db["users"]
            self.orders = self.db["orders"]
            self.deposits = self.db["deposits"]
            self.config = self.db["config"]
            
            # Create indexes
            self.users.create_index("userId", unique=True)
            self.orders.create_index("orderId", unique=True)
            self.orders.create_index("userId")
            self.deposits.create_index("userId")
            self.deposits.create_index("status")
            self.config.create_index("key", unique=True)
            
            print("✅ MongoDB Connected Successfully!")
            
        except Exception as e:
            print(f"❌ MongoDB Connection Error: {e}")
            raise

    # ──────────── User Functions ────────────
    
    def create_user(self, user_id, username=None, first_name=None):
        """Create new user if not exists"""
        existing_user = self.users.find_one({"userId": user_id})
        
        if not existing_user:
            new_user = {
                "userId": user_id,
                "username": username,
                "firstName": first_name,
                "balance": 0.0,
                "totalOrders": 0,
                "totalDeposits": 0,
                "createdAt": self.get_current_time(),
                "isAdmin": False,
                "isBanned": False
            }
            self.users.insert_one(new_user)
            return new_user
        return existing_user

    def get_user(self, user_id):
        """Get user by ID"""
        return self.users.find_one({"userId": user_id})

    def get_user_balance(self, user_id):
        """Get user balance"""
        user = self.get_user(user_id)
        return user["balance"] if user else 0.0

    def update_balance(self, user_id, amount):
        """Update user balance (add or deduct)"""
        result = self.users.update_one(
            {"userId": user_id},
            {"$inc": {"balance": amount}}
        )
        return result.modified_count > 0

    def increment_orders(self, user_id):
        """Increment total orders count"""
        result = self.users.update_one(
            {"userId": user_id},
            {"$inc": {"totalOrders": 1}}
        )
        return result.modified_count > 0

    def increment_deposits(self, user_id):
        """Increment total deposits count"""
        result = self.users.update_one(
            {"userId": user_id},
            {"$inc": {"totalDeposits": 1}}
        )
        return result.modified_count > 0

    def get_all_users(self, limit=100):
        """Get all users with limit"""
        return list(self.users.find().limit(limit))

    def get_top_users(self, limit=10):
        """Get top users by total orders"""
        return list(self.users.find().sort("totalOrders", -1).limit(limit))

    def update_user_username(self, user_id, username):
        """Update user's username"""
        self.users.update_one(
            {"userId": user_id},
            {"$set": {"username": username}}
        )

    # ──────────── Order Functions ────────────
    
    def create_order(self, user_id, player_id, amount, product_name=None, product_code=None):
        """Create new order"""
        from datetime import datetime
        import random
        
        order_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
        
        new_order = {
            "orderId": order_id,
            "userId": user_id,
            "playerId": player_id,
            "amount": float(amount),
            "productName": product_name,
            "productCode": product_code,
            "status": "pending",
            "apiStatus": None,
            "apiMessage": None,
            "reference": None,
            "gameName": None,
            "gameZoneId": None,
            "balanceBefore": None,
            "balanceAfter": None,
            "createdAt": self.get_current_time(),
            "completedAt": None,
            "rawResponse": None
        }
        
        self.orders.insert_one(new_order)
        self.increment_orders(user_id)
        return new_order

    def update_order_with_api_response(self, order_id, api_response):
        """Update order with API response"""
        is_success = api_response.get("status") == "SUCCESS"
        
        update_data = {
            "apiStatus": api_response.get("status"),
            "apiMessage": api_response.get("message"),
            "reference": api_response.get("reference"),
            "gameName": api_response.get("game_name"),
            "balanceBefore": api_response.get("balance_before"),
            "balanceAfter": api_response.get("balance_after"),
            "rawResponse": api_response
        }
        
        if is_success:
            update_data["status"] = "completed"
            update_data["completedAt"] = api_response.get("completed_at") or self.get_current_time()
        else:
            update_data["status"] = "failed"
        
        result = self.orders.update_one(
            {"orderId": order_id},
            {"$set": update_data}
        )
        return result.modified_count > 0

    def get_order_by_reference(self, reference):
        """Get order by reference"""
        return self.orders.find_one({"reference": reference})

    def get_user_orders_by_status(self, user_id, status=None, limit=20):
        """Get user orders by status"""
        query = {"userId": user_id}
        if status:
            query["status"] = status
        
        return list(self.orders.find(query).sort("createdAt", -1).limit(limit))

    def get_recent_orders(self, limit=50):
        """Get recent orders for admin"""
        return list(self.orders.find().sort("createdAt", -1).limit(limit))

    def get_orders_by_date(self, start_date, end_date):
        """Get orders between dates"""
        query = {
            "createdAt": {
                "$gte": start_date,
                "$lte": end_date
            }
        }
        return list(self.orders.find(query).sort("createdAt", -1))

    def get_user_orders(self, user_id, limit=20):
        """Get user's orders"""
        return list(self.orders.find(
            {"userId": user_id}
        ).sort("createdAt", -1).limit(limit))

    def get_order(self, order_id):
        """Get order by ID"""
        return self.orders.find_one({"orderId": order_id})

    def update_order_status(self, order_id, status):
        """Update order status"""
        update_data = {"status": status}
        if status == "completed":
            update_data["completedAt"] = self.get_current_time()
        
        result = self.orders.update_one(
            {"orderId": order_id},
            {"$set": update_data}
        )
        return result.modified_count > 0

    def get_total_revenue(self):
        """Get total revenue from completed orders"""
        pipeline = [
            {"$match": {"status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$amountLKR"}}}
        ]
        result = list(self.orders.aggregate(pipeline))
        return result[0]["total"] if result else 0.0

    # ──────────── Deposit Functions ────────────
    
    def create_deposit(self, user_id, amount, receipt, reference=None):
        """Create new deposit request"""
        new_deposit = {
            "userId": user_id,
            "amount": float(amount),
            "receipt": receipt,
            "reference": reference,
            "method": "unknown",
            "status": "pending",
            "createdAt": self.get_current_time(),
            "approvedAt": None,
            "approvedBy": None
        }
        
        self.deposits.insert_one(new_deposit)
        self.increment_deposits(user_id)
        return new_deposit

    def get_user_deposits(self, user_id, limit=20):
        """Get user's deposits"""
        return list(self.deposits.find(
            {"userId": user_id}
        ).sort("createdAt", -1).limit(limit))

    def get_pending_deposits(self):
        """Get all pending deposits"""
        return list(self.deposits.find({"status": "pending"}).sort("createdAt", 1))

    def approve_deposit(self, deposit_id, admin_id):
        """Approve deposit and add balance to user (uses existing amount)"""
        from bson import ObjectId
        
        try:
            deposit = self.deposits.find_one({"_id": ObjectId(deposit_id)})
        except:
            return False, "Invalid deposit ID"
        
        if not deposit:
            return False, "Deposit not found"
        
        if deposit["status"] != "pending":
            return False, "Deposit already processed"
        
        amount = deposit.get("amount", 0)
        if amount <= 0:
            return False, "Deposit amount is 0. Please use /approve <id> <amount>"
        
        # Update deposit status
        self.deposits.update_one(
            {"_id": ObjectId(deposit_id)},
            {
                "$set": {
                    "status": "approved",
                    "approvedAt": self.get_current_time(),
                    "approvedBy": admin_id
                }
            }
        )
        
        # Add balance to user
        user_id = deposit["userId"]
        self.update_balance(user_id, amount)
        
        return True, f"Deposit approved successfully! Added {amount:.2f} LKR to user"

    def approve_deposit_with_amount(self, deposit_id, admin_id, amount):
        """Approve deposit with specific amount and add balance to user"""
        from bson import ObjectId
        
        try:
            deposit = self.deposits.find_one({"_id": ObjectId(deposit_id)})
        except:
            return False, "Invalid deposit ID"
        
        if not deposit:
            return False, "Deposit not found"
        
        if deposit["status"] != "pending":
            return False, "Deposit already processed"
        
        if amount <= 0:
            return False, "Amount must be positive!"
        
        # Update deposit with amount
        self.deposits.update_one(
            {"_id": ObjectId(deposit_id)},
            {
                "$set": {
                    "status": "approved",
                    "amount": amount,
                    "approvedAt": self.get_current_time(),
                    "approvedBy": admin_id
                }
            }
        )
        
        # Add balance to user
        user_id = deposit["userId"]
        self.update_balance(user_id, amount)
        
        return True, f"Deposit approved successfully! Added {amount:.2f} LKR to user"

    def reject_deposit(self, deposit_id, admin_id):
        """Reject deposit"""
        from bson import ObjectId
        
        try:
            deposit_id_obj = ObjectId(deposit_id)
        except:
            return False
        
        result = self.deposits.update_one(
            {"_id": deposit_id_obj},
            {
                "$set": {
                    "status": "rejected",
                    "approvedAt": self.get_current_time(),
                    "approvedBy": admin_id
                }
            }
        )
        return result.modified_count > 0

    # ──────────── Admin Functions ────────────
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        user = self.get_user(user_id)
        return user and user.get("isAdmin", False)

    def set_admin(self, user_id, is_admin=True):
        """Set user as admin"""
        self.users.update_one(
            {"userId": user_id},
            {"$set": {"isAdmin": is_admin}}
        )

    def ban_user(self, user_id):
        """Ban user"""
        self.users.update_one(
            {"userId": user_id},
            {"$set": {"isBanned": True}}
        )

    def unban_user(self, user_id):
        """Unban user"""
        self.users.update_one(
            {"userId": user_id},
            {"$set": {"isBanned": False}}
        )

    # ──────────── Config Functions ────────────
    
    def get_bot_config(self):
        """Get bot configuration"""
        config = self.config.find_one({"key": "bot_config"})
        
        if config:
            return config.get("value", {})
        
        default_config = {
            "usdToLkrRate": 349.693,
            "minDeposit": 100,
            "maxDeposit": 50000,
            "updatedAt": self.get_current_time()
        }
        
        self.config.update_one(
            {"key": "bot_config"},
            {"$set": {"key": "bot_config", "value": default_config}},
            {"upsert": True}
        )
        
        return default_config
    
    def update_bot_config(self, new_config):
        """Update bot configuration"""
        try:
            new_config["updatedAt"] = self.get_current_time()
            self.config.update_one(
                {"key": "bot_config"},
                {"$set": {"key": "bot_config", "value": new_config}},
                {"upsert": True}
            )
            return True
        except Exception as e:
            print(f"❌ Error updating config: {e}")
            return False
    
    def get_usd_to_lkr_rate(self):
        """Get USD to LKR conversion rate"""
        config = self.get_bot_config()
        return config.get("usdToLkrRate", 349.693)
    
    def get_deposit_limits(self):
        """Get min and max deposit limits"""
        config = self.get_bot_config()
        return {
            "min": config.get("minDeposit", 100),
            "max": config.get("maxDeposit", 50000)
        }

    # ──────────── Utility Functions ────────────
    
    def get_current_time(self):
        """Get current time in ISO format"""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_stats(self):
        """Get bot statistics"""
        total_users = self.users.count_documents({})
        total_orders = self.orders.count_documents({})
        total_deposits = self.deposits.count_documents({})
        pending_deposits = self.deposits.count_documents({"status": "pending"})
        total_revenue = self.get_total_revenue()
        
        return {
            "totalUsers": total_users,
            "totalOrders": total_orders,
            "totalDeposits": total_deposits,
            "pendingDeposits": pending_deposits,
            "totalRevenue": total_revenue
        }

# Initialize database connection
db = Database()
