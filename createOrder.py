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
DEFAULT_USD_TO_LKR_RATE = 355.8201058201058  # Default rate if database fails

class OrderManager:
    """Manage order creation and processing"""
    
    def __init__(self):
        self.api_url = BAY2GAME_API_URL
        self.api_key = BAY2GAME_API_KEY
        self.default_usd_rate = DEFAULT_USD_TO_LKR_RATE
    
    def get_usd_rate(self) -> float:
        """
        Get USD to LKR rate from database
        If not available, use default rate
        """
        try:
            rate = db.get_usd_to_lkr_rate()
            return rate
        except Exception as e:
            logger.warning(f"Could not get USD rate from database: {e}, using default: {self.default_usd_rate}")
            return self.default_usd_rate
    
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
    
    def convert_usd_to_lkr(self, usd_price: float) -> float:
        """
        Convert USD to LKR using database rate
        
        Args:
            usd_price: Price in USD
        
        Returns:
            Price in LKR (rounded to 2 decimal places)
        """
        rate = self.get_usd_rate()
        return round(usd_price * rate, 2)
    
    async def check_user_balance(self, user_id: int, product_price_lkr: float) -> Tuple[bool, float, str]:
        """
        Check if user has sufficient balance
        
        Args:
            user_id: Telegram user ID
            product_price_lkr: Price in LKR
        
        Returns:
            Tuple of (has_balance, current_balance, message)
        """
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
        amount_usd: float = 0
    ) -> Dict:
        """
        Create order with Bay2Game API
        
        Args:
            user_id: Telegram user ID
            product_code: Product code from API (e.g., FREEFIRE_SG_25)
            game_user_id: Player ID
            game_zone_id: Zone/Server ID (optional)
            product_name: Product name
            amount_usd: Price in USD (for database)
        
        Returns:
            API response as dict
        """
        try:
            # Generate unique reference
            reference = self.generate_reference()
            
            # Prepare API parameters - using correct product code
            params = {
                'api_key': self.api_key,
                'product_code': product_code,
                'game_user_id': game_user_id,
                'reference': reference
            }
            
            # Add zone ID if provided (for games that need it)
            if game_zone_id:
                params['game_zone_id'] = game_zone_id
            
            logger.info(f"📤 Creating order with params: {params}")
            
            # Make API request
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                api_response = response.json()
                
                logger.info(f"📥 API Response: {api_response}")
                
                # Check if order was successful - FIXED: Check both "success" and "SUCCESS"
                api_status = api_response.get("status", "")
                is_success = api_status in ["success", "SUCCESS", "Success"]
                
                # Save order to database
                order = self.save_order_to_database(
                    user_id=user_id,
                    product_code=product_code,
                    game_user_id=game_user_id,
                    game_zone_id=game_zone_id,
                    product_name=product_name,
                    amount_usd=amount_usd,
                    reference=reference,
                    api_response=api_response,
                    is_success=is_success
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
    
    def save_order_to_database(
        self,
        user_id: int,
        product_code: str,
        game_user_id: str,
        game_zone_id: Optional[str],
        product_name: str,
        amount_usd: float,
        reference: str,
        api_response: Dict,
        is_success: bool
    ) -> Dict:
        """
        Save order to database and deduct balance if successful
        """
        order_id = self.generate_order_id()
        
        # Convert USD to LKR using database rate
        amount_lkr = self.convert_usd_to_lkr(amount_usd)
        
        # Get user before deduction
        user = db.get_user(user_id)
        balance_before = user.get("balance", 0.0) if user else 0.0
        
        # Calculate balance after deduction
        balance_after = balance_before - amount_lkr if is_success else balance_before
        
        # Get API status
        api_status = api_response.get("status", "")
        
        # Prepare order data
        new_order = {
            "orderId": order_id,
            "userId": user_id,
            "reference": reference,
            "productCode": product_code,
            "productName": product_name or api_response.get("product_name", "Unknown"),
            "playerId": game_user_id,
            "gameZoneId": game_zone_id,
            "gameName": api_response.get("game_name", "FreeFire SG"),
            "amountUSD": amount_usd,
            "amountLKR": amount_lkr,
            "status": "completed" if is_success else "failed",
            "apiStatus": api_status,
            "apiMessage": api_response.get("message", ""),
            "balanceBefore": balance_before,
            "balanceAfter": balance_after,
            "apiBalanceBefore": api_response.get("balance_before", 0),
            "apiBalanceAfter": api_response.get("balance_after", 0),
            "createdAt": db.get_current_time(),
            "completedAt": api_response.get("completed_at") or db.get_current_time() if is_success else None,
            "rawResponse": api_response,
            "rateUsed": self.get_usd_rate()  # Store which rate was used
        }
        
        # Insert into database
        db.orders.insert_one(new_order)
        
        # Increment user's total orders
        db.increment_orders(user_id)
        
        # ─── Deduct balance if successful ───
        if is_success:
            # Deduct LKR amount from user balance
            update_result = db.update_balance(user_id, -amount_lkr)
            
            if update_result:
                logger.info(f"✅ Order {order_id} completed. Deducted {amount_lkr:.2f} LKR from user {user_id}")
                logger.info(f"💰 Balance: {balance_before:.2f} → {balance_after:.2f} LKR")
                logger.info(f"📊 Rate used: {self.get_usd_rate()}")
            else:
                logger.error(f"❌ Failed to deduct balance for order {order_id}")
                # Update order status to failed if balance deduction failed
                db.orders.update_one(
                    {"orderId": order_id},
                    {"$set": {"status": "failed", "apiMessage": "Balance deduction failed"}}
                )
                new_order["status"] = "failed"
        else:
            logger.warning(f"⚠️ Order {order_id} failed. No balance deducted.")
            logger.info(f"💰 Balance unchanged: {balance_before:.2f} LKR")
        
        return new_order
    
    async def process_order(
        self,
        user_id: int,
        product_code: str,
        game_user_id: str,
        game_zone_id: Optional[str] = None,
        product_name: str = None,
        price_usd: float = 0
    ) -> Dict:
        """
        Full order processing flow
        
        Args:
            user_id: Telegram user ID
            product_code: Product code (e.g., FREEFIRE_SG_25)
            game_user_id: Player ID
            game_zone_id: Zone ID (optional)
            product_name: Product name
            price_usd: Price in USD
        
        Returns:
            Dict with order result
        """
        # Get current rate for logging
        current_rate = self.get_usd_rate()
        logger.info(f"💰 Using USD to LKR rate: {current_rate}")
        
        # 1. Check if user exists and has balance
        price_lkr = self.convert_usd_to_lkr(price_usd)
        has_balance, current_balance, balance_msg = await self.check_user_balance(
            user_id, price_lkr
        )
        
        if not has_balance:
            return {
                "success": False,
                "error": balance_msg,
                "current_balance": current_balance
            }
        
        # 2. Create order with API
        result = await self.create_order_with_api(
            user_id=user_id,
            product_code=product_code,
            game_user_id=game_user_id,
            game_zone_id=game_zone_id,
            product_name=product_name,
            amount_usd=price_usd
        )
        
        return result

# ──────────────────────────────
# Singleton instance
# ──────────────────────────────

order_manager = OrderManager()

# ──────────────────────────────
# Utility Functions for Bot
# ──────────────────────────────

async def process_product_purchase(
    user_id: int,
    product_id: int,
    game_user_id: str,
    game_zone_id: Optional[str] = None
) -> Dict:
    """
    Process product purchase from product ID
    
    Args:
        user_id: Telegram user ID
        product_id: Product ID from Bay2Game
        game_user_id: Player ID
        game_zone_id: Zone ID (optional)
    
    Returns:
        Purchase result
    """
    from products import product_manager
    
    # Get product details
    product = product_manager.get_product_by_id(product_id)
    
    if not product:
        return {
            "success": False,
            "error": "Product not found. Please try again.",
            "step": "product_not_found"
        }
    
    # Extract product info
    product_code = product.get("product_code")
    product_name = product.get("name")
    price_usd = product.get("sell_price_usd", 0)
    price_lkr = product.get("sell_price_lkr", 0)
    
    logger.info(f"📦 Processing purchase: {product_code} - {product_name}")
    logger.info(f"💰 Price: ${price_usd} (Rs. {price_lkr})")
    
    # Process order
    result = await order_manager.process_order(
        user_id=user_id,
        product_code=product_code,
        game_user_id=game_user_id,
        game_zone_id=game_zone_id,
        product_name=product_name,
        price_usd=price_usd
    )
    
    return result

def format_order_result(result: Dict) -> str:
    """
    Format order result for user display
    """
    if not result.get("success"):
        return result.get("error", "❌ Order failed. Please try again.")
    
    api_response = result.get("api_response", {})
    order = result.get("order", {})
    
    # Check if order was successful - supports both "success" and "SUCCESS"
    api_status = api_response.get("status", "")
    is_success = api_status in ["success", "SUCCESS", "Success"]
    
    if is_success:
        text = (
            f"✅ **Order Successful!**\n\n"
            f"🆔 Order ID: `{order.get('orderId')}`\n"
            f"📝 Product: {order.get('productName')}\n"
            f"🎮 Game: {order.get('gameName', 'FreeFire SG')}\n"
            f"🎯 Player ID: {order.get('playerId')}\n"
            f"💰 Amount: ${order.get('amountUSD', 0):.2f} (Rs. {order.get('amountLKR', 0):,.2f})\n"
            f"💵 Balance: Rs. {order.get('balanceBefore', 0):,.2f} → Rs. {order.get('balanceAfter', 0):,.2f}\n"
            f"📅 Completed: {order.get('completedAt', 'N/A')[:10]}\n\n"
            f"✅ Your order has been processed successfully!"
        )
    else:
        text = (
            f"❌ **Order Failed!**\n\n"
            f"📝 Product: {order.get('productName', 'Unknown')}\n"
            f"🎯 Player ID: {order.get('playerId')}\n"
            f"💬 Reason: {api_response.get('message', 'Unknown error')}\n\n"
            f"⚠️ Please try again or contact support."
        )
    
    return text

def format_order_for_admin(order: Dict) -> str:
    """
    Format order for admin display
    """
    status_emoji = "✅" if order.get("status") == "completed" else "❌"
    
    text = (
        f"{status_emoji} **Order {order.get('orderId')}**\n"
        f"├ 👤 User ID: `{order.get('userId')}`\n"
        f"├ 📝 Product: {order.get('productName')}\n"
        f"├ 🎯 Player: {order.get('playerId')}\n"
        f"├ 💰 Amount: ${order.get('amountUSD', 0):.2f}\n"
        f"├ 📊 Status: {order.get('status').upper()}\n"
        f"└ 📅 Created: {order.get('createdAt', 'N/A')[:10]}\n"
    )
    
    return text

# ──────────────────────────────
# Test function
# ──────────────────────────────

async def test_order_creation():
    """Test order creation with correct product code"""
    print("=" * 50)
    print("🔄 Testing Order Creation")
    print("=" * 50)
    
    # Get current rate
    rate = order_manager.get_usd_rate()
    print(f"💰 Current USD to LKR Rate: {rate}")
    
    # Test data - using correct product codes
    test_user_id = 123456789
    test_product_code = "FREEFIRE_SG_25"
    test_player_id = "123456789"
    test_price_usd = 0.25
    
    print(f"\n📝 Test Order Details:")
    print(f"├ User ID: {test_user_id}")
    print(f"├ Product Code: {test_product_code}")
    print(f"├ Player ID: {test_player_id}")
    print(f"├ Price: ${test_price_usd}")
    print(f"└ Rate: {rate}")
    
    print("\n⏳ Processing order...")
    
    result = await order_manager.process_order(
        user_id=test_user_id,
        product_code=test_product_code,
        game_user_id=test_player_id,
        game_zone_id=None,
        product_name="25 Diamonds",
        price_usd=test_price_usd
    )
    
    print("\n📊 Result:")
    if result.get("success"):
        print("✅ Order successful!")
        order = result.get("order", {})
        print(f"├ Order ID: {order.get('orderId')}")
        print(f"├ Status: {order.get('status')}")
        print(f"├ Balance Before: Rs. {order.get('balanceBefore', 0):,.2f}")
        print(f"├ Balance After: Rs. {order.get('balanceAfter', 0):,.2f}")
        print(f"├ Rate Used: {order.get('rateUsed', 'N/A')}")
        print(f"└ Reference: {order.get('reference')}")
    else:
        print(f"❌ Order failed: {result.get('error')}")

# ──────────────────────────────
# Main
# ──────────────────────────────

if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_order_creation())
