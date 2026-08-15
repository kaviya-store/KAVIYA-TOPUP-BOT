import os
import httpx
import logging
import random
from datetime import datetime
from typing import Dict, Optional, Tuple
from database import db

logger = logging.getLogger(__name__)

# ──────────────────────────────
# Config
# ──────────────────────────────

BAY2GAME_API_URL = "https://api.bay2game.xyz/api/create_order"
BAY2GAME_API_KEY = "498185DF8D4C27DB67D5216A"

class OrderManager:
    """Manage order creation and processing"""
    
    def __init__(self):
        self.api_url = BAY2GAME_API_URL
        self.api_key = BAY2GAME_API_KEY
    
    def generate_order_id(self) -> str:
        """Generate unique order ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_num = random.randint(1000, 9999)
        return f"ZANTA{timestamp}{random_num}"
    
    def generate_reference(self) -> str:
        """Generate unique reference for API"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_num = random.randint(100000, 999999)
        return f"REF{timestamp}{random_num}"
    
    async def check_user_balance(self, user_id: int, product_price_lkr: float) -> Tuple[bool, float, str]:
        """Check if user has sufficient balance"""
        user = db.get_user(user_id)
        
        if not user:
            return False, 0.0, "❌ User not found! Please /start first."
        
        current_balance = user.get("balance", 0.0)
        
        if current_balance < product_price_lkr:
            return False, current_balance, (
                f"❌ **Insufficient Balance!**\n\n"
                f"💰 Required: **{product_price_lkr:.2f}** LKR\n"
                f"💵 Your Balance: **{current_balance:.2f}** LKR\n"
                f"💳 Need: **{product_price_lkr - current_balance:.2f}** LKR more\n\n"
                f"Please deposit first to continue."
            )
        
        return True, current_balance, "✅ Balance sufficient"
    
    async def create_order_with_api(
        self,
        user_id: int,
        product_code: str,
        game_user_id: str,
        game_zone_id: Optional[str] = None,
        product_name: str = None,
        amount_lkr: float = 0,
        game_code: str = "freefire_sgmy"
    ) -> Dict:
        """Create order with Bay2Game API"""
        try:
            reference = self.generate_reference()
            
            params = {
                'api_key': self.api_key,
                'product_code': product_code,
                'game_user_id': game_user_id,
                'reference': reference,
                'game_code': game_code
            }
            
            if game_zone_id:
                params['game_zone_id'] = game_zone_id
            
            logger.info(f"📤 Creating order with params: {params}")
            logger.info(f"🎮 Game Code: {game_code}")
            
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                api_response = response.json()
                
                logger.info(f"📥 API Response: {api_response}")
                
                api_status = api_response.get("status", "")
                is_success = api_status in ["success", "SUCCESS", "Success"]
                
                order = self.save_order_to_database_atomic(
                    user_id=user_id,
                    product_code=product_code,
                    game_user_id=game_user_id,
                    game_zone_id=game_zone_id,
                    product_name=product_name,
                    amount_lkr=amount_lkr,
                    reference=reference,
                    api_response=api_response,
                    is_success=is_success,
                    game_code=game_code
                )
                
                return {
                    "success": is_success,
                    "api_response": api_response,
                    "order": order
                }
                
        except httpx.TimeoutException:
            logger.error("API request timeout")
            return {
                "success": False,
                "error": "API request timeout. Please try again.",
                "api_response": None
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            return {
                "success": False,
                "error": f"HTTP error: {e.response.status_code}",
                "api_response": None
            }
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return {
                "success": False,
                "error": f"Error: {str(e)}",
                "api_response": None
            }
    
    def save_order_to_database_atomic(
        self,
        user_id: int,
        product_code: str,
        game_user_id: str,
        game_zone_id: Optional[str],
        product_name: str,
        amount_lkr: float,
        reference: str,
        api_response: Dict,
        is_success: bool,
        game_code: str = "freefire_sg"
    ) -> Dict:
        """
        Save order to database with ATOMIC balance deduction
        """
        order_id = self.generate_order_id()
        
        # Get user before deduction
        user = db.get_user(user_id)
        if not user:
            logger.error(f"❌ User {user_id} not found!")
            return {
                "orderId": order_id,
                "status": "failed",
                "error": "User not found"
            }
        
        balance_before = user.get("balance", 0.0)
        api_status = api_response.get("status", "")
        
        # ─── Prepare order data ───
        new_order = {
            "orderId": order_id,
            "userId": user_id,
            "reference": reference,
            "productCode": product_code,
            "productName": product_name or api_response.get("product_name", "Unknown"),
            "playerId": game_user_id,
            "gameZoneId": game_zone_id,
            "gameName": api_response.get("game_name", "FreeFire SG"),
            "gameCode": game_code,
            "amountUSD": api_response.get("amount", 0),
            "amountLKR": amount_lkr,
            "status": "pending",
            "apiStatus": api_status,
            "apiMessage": api_response.get("message", ""),
            "balanceBefore": balance_before,
            "balanceAfter": balance_before,
            "apiBalanceBefore": api_response.get("balance_before", 0),
            "apiBalanceAfter": api_response.get("balance_after", 0),
            "createdAt": db.get_current_time(),
            "completedAt": None,
            "rawResponse": api_response
        }
        
        # ─── If API success, deduct balance ───
        if is_success:
            deduct_success, deduct_message, new_balance = self._deduct_balance_safe(
                user_id, amount_lkr, balance_before
            )
            
            if deduct_success:
                new_order["status"] = "completed"
                new_order["balanceAfter"] = new_balance
                new_order["completedAt"] = api_response.get("completed_at") or db.get_current_time()
                new_order["apiMessage"] = "Order completed successfully"
                
                db.increment_orders(user_id)
                
                logger.info(f"✅ Order {order_id} COMPLETED. Deducted {amount_lkr:.2f} LKR")
                logger.info(f"💰 Balance: {balance_before:.2f} → {new_balance:.2f} LKR")
            else:
                new_order["status"] = "failed"
                new_order["balanceAfter"] = balance_before
                new_order["apiMessage"] = f"Balance deduction failed: {deduct_message}"
                
                logger.error(f"❌ Order {order_id} FAILED. {deduct_message}")
        else:
            new_order["status"] = "failed"
            new_order["balanceAfter"] = balance_before
            new_order["apiMessage"] = api_response.get("message", "API order failed")
            
            logger.warning(f"⚠️ Order {order_id} FAILED. API error: {new_order['apiMessage']}")
        
        # ─── Save order to database ───
        db.orders.insert_one(new_order)
        
        return new_order
    
    def _deduct_balance_safe(self, user_id: int, amount: float, current_balance: float) -> Tuple[bool, str, float]:
        """
        Safely deduct balance from user
        
        Returns: (success, message, new_balance)
        """
        try:
            if current_balance < amount:
                return False, f"Insufficient balance. Required: {amount}, Available: {current_balance}", current_balance
            
            result = db.users.update_one(
                {"userId": user_id},
                {"$inc": {"balance": -amount}}
            )
            
            if result.modified_count > 0:
                new_balance = current_balance - amount
                return True, "Balance deducted successfully", new_balance
            else:
                return False, "Failed to update balance in database", current_balance
                
        except Exception as e:
            logger.error(f"Error deducting balance: {e}")
            return False, f"Database error: {str(e)}", current_balance
    
    async def process_order(
        self,
        user_id: int,
        product_code: str,
        game_user_id: str,
        game_zone_id: Optional[str] = None,
        product_name: str = None,
        price_lkr: float = 0,
        game_code: str = "freefire_sg"
    ) -> Dict:
        """Full order processing flow"""
        has_balance, current_balance, balance_msg = await self.check_user_balance(
            user_id, price_lkr
        )
        
        if not has_balance:
            return {
                "success": False,
                "error": balance_msg,
                "current_balance": current_balance
            }
        
        result = await self.create_order_with_api(
            user_id=user_id,
            product_code=product_code,
            game_user_id=game_user_id,
            game_zone_id=game_zone_id,
            product_name=product_name,
            amount_lkr=price_lkr,
            game_code=game_code
        )
        
        return result

# ──────────────────────────────
# Create instance (SINGLETON)
# ──────────────────────────────

order_manager = OrderManager()

# ──────────────────────────────
# Utility Functions for Bot
# ──────────────────────────────

async def process_product_purchase(
    user_id: int,
    product_id: int,
    game_user_id: str,
    game_zone_id: Optional[str] = None,
    game_code: str = "freefire_sg"
) -> Dict:
    """Process product purchase from product ID"""
    from products import product_manager
    
    product = product_manager.get_product_by_id(product_id, user_id)
    
    if not product:
        return {
            "success": False,
            "error": "Product not found. Please try again.",
            "step": "product_not_found"
        }
    
    product_code = product.get("product_code")
    product_name = product.get("name")
    price_lkr = product.get("sell_price_lkr", 0)
    
    logger.info(f"📦 Processing purchase: {product_code} - {product_name}")
    logger.info(f"💰 Price: Rs. {price_lkr:.2f}")
    logger.info(f"🎮 Game Code: {game_code}")
    
    result = await order_manager.process_order(
        user_id=user_id,
        product_code=product_code,
        game_user_id=game_user_id,
        game_zone_id=game_zone_id,
        product_name=product_name,
        price_lkr=price_lkr,
        game_code=game_code
    )
    
    return result

def format_order_result(result: Dict) -> str:
    """Format order result for user display"""
    if not result.get("success"):
        return result.get("error", "❌ Order failed. Please try again.")
    
    order = result.get("order", {})
    status = order.get("status", "unknown")
    game_code = order.get("gameCode", "freefire_sg")
    
    game_display = "FreeFire SG" if game_code == "freefire_sg" else "FreeFire SG MY"
    
    if status == "completed":
        text = (
            f"✅ **Order Successful!**\n\n"
            f"🆔 Order ID: `{order.get('orderId')}`\n"
            f"📝 Product: {order.get('productName')}\n"
            f"🎮 Game: {game_display}\n"
            f"🎯 Player ID: {order.get('playerId')}\n"
            f"💰 Amount: Rs. {order.get('amountLKR', 0):,.2f}\n"
            f"💵 Balance: Rs. {order.get('balanceBefore', 0):,.2f} → Rs. {order.get('balanceAfter', 0):,.2f}\n"
            f"📅 Completed: {order.get('completedAt', 'N/A')[:10]}\n\n"
            f"✅ Your order has been processed successfully!"
        )
    elif status == "pending":
        text = (
            f"⏳ **Order Pending!**\n\n"
            f"🆔 Order ID: `{order.get('orderId')}`\n"
            f"📝 Product: {order.get('productName')}\n"
            f"🎯 Player ID: {order.get('playerId')}\n"
            f"💰 Amount: Rs. {order.get('amountLKR', 0):,.2f}\n\n"
            f"⏳ Your order is being processed. Please wait."
        )
    else:
        text = (
            f"❌ **Order Failed!**\n\n"
            f"📝 Product: {order.get('productName', 'Unknown')}\n"
            f"🎯 Player ID: {order.get('playerId')}\n"
            f"💬 Reason: {order.get('apiMessage', 'Unknown error')}\n\n"
            f"⚠️ Please try again or contact support."
        )
    
    return text

def format_order_for_admin(order: Dict) -> str:
    """Format order for admin display"""
    status_emoji = {
        "completed": "✅",
        "pending": "⏳",
        "failed": "❌"
    }.get(order.get("status"), "❓")
    
    text = (
        f"{status_emoji} **Order {order.get('orderId')}**\n"
        f"├ 👤 User ID: `{order.get('userId')}`\n"
        f"├ 📝 Product: {order.get('productName')}\n"
        f"├ 🎯 Player: {order.get('playerId')}\n"
        f"├ 💰 Amount: Rs. {order.get('amountLKR', 0):,.2f}\n"
        f"├ 📊 Status: {order.get('status', 'unknown').upper()}\n"
        f"├ 💬 Message: {order.get('apiMessage', 'N/A')}\n"
        f"└ 📅 Created: {order.get('createdAt', 'N/A')[:10]}\n"
    )
    
    return text

# ──────────────────────────────
# Test function
# ──────────────────────────────

async def test_order_creation():
    """Test order creation"""
    print("=" * 50)
    print("🔄 Testing Order Creation")
    print("=" * 50)
    
    test_user_id = 123456789
    test_product_code = "FREEFIRE_SG_25"
    test_player_id = "123456789"
    test_price_lkr = 120
    
    print(f"\n📝 Test Order Details:")
    print(f"├ User ID: {test_user_id}")
    print(f"├ Product Code: {test_product_code}")
    print(f"├ Player ID: {test_player_id}")
    print(f"└ Price: Rs. {test_price_lkr:.2f}")
    
    print("\n⏳ Processing order...")
    
    result = await order_manager.process_order(
        user_id=test_user_id,
        product_code=test_product_code,
        game_user_id=test_player_id,
        game_zone_id=None,
        product_name="25 Diamonds",
        price_lkr=test_price_lkr
    )
    
    print("\n📊 Result:")
    if result.get("success"):
        print("✅ Order successful!")
        order = result.get("order", {})
        print(f"├ Order ID: {order.get('orderId')}")
        print(f"├ Status: {order.get('status')}")
        print(f"├ Balance Before: Rs. {order.get('balanceBefore', 0):,.2f}")
        print(f"├ Balance After: Rs. {order.get('balanceAfter', 0):,.2f}")
        print(f"└ Reference: {order.get('reference')}")
    else:
        print(f"❌ Order failed: {result.get('error')}")

async def test_sgmy_order():
    """Test SG MY order creation"""
    print("=" * 50)
    print("🔄 Testing SG MY Order Creation")
    print("=" * 50)
    
    test_user_id = 123456789
    test_product_code = "FREEFIRE_SGMY_Level_Up_Package___Level_6"
    test_player_id = "123456789"
    test_price_lkr = 110
    
    print(f"\n📝 Test Order Details:")
    print(f"├ User ID: {test_user_id}")
    print(f"├ Product Code: {test_product_code}")
    print(f"├ Player ID: {test_player_id}")
    print(f"└ Price: Rs. {test_price_lkr:.2f}")
    print(f"└ Game Code: freefire_sgmy")
    
    print("\n⏳ Processing order...")
    
    result = await order_manager.process_order(
        user_id=test_user_id,
        product_code=test_product_code,
        game_user_id=test_player_id,
        game_zone_id=None,
        product_name="Level 6",
        price_lkr=test_price_lkr,
        game_code="freefire_sgmy"
    )
    
    print("\n📊 Result:")
    if result.get("success"):
        print("✅ Order successful!")
        order = result.get("order", {})
        print(f"├ Order ID: {order.get('orderId')}")
        print(f"├ Status: {order.get('status')}")
        print(f"├ Game Code: {order.get('gameCode')}")
        print(f"├ Balance Before: Rs. {order.get('balanceBefore', 0):,.2f}")
        print(f"├ Balance After: Rs. {order.get('balanceAfter', 0):,.2f}")
        print(f"└ Reference: {order.get('reference')}")
    else:
        print(f"❌ Order failed: {result.get('error')}")

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_order_creation())
