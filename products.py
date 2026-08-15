import os
import httpx
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ──────────────────────────────
# Config
# ──────────────────────────────

BAY2GAME_API_URL = "https://api.bay2game.xyz/api/products"
BAY2GAME_API_KEY = "498185DF8D4C27DB67D5216A"

# Allowed products - only these will be shown
ALLOWED_PRODUCTS = [
    # Diamond Packs
    "FREEFIRE_SGMY_25",
    "FREEFIRE_SGMY_100",
    "FREEFIRE_SGMY_310",
    "FREEFIRE_SGMY_520",
    "FREEFIRE_SGMY_1060",
    "FREEFIRE_SGMY_2180",
    "FREEFIRE_SGMY_5600",
    "FREEFIRE_SGMY_11500",
    
    # Memberships
    "FREEFIRE_SGMY_Weekly",
    "FREEFIRE_SGMY_WeeklyLite",
    "UNGS_FFSG_Monthly",
    
    # Level Up Packages
    "FREEFIRE_SGMY_Level_Up_Package___Level_6",
    "FREEFIRE_SGMY_Level_Up_Package___Level_10",
    "FREEFIRE_SGMY_Level_Up_Package___Level_15",
    "FREEFIRE_SGMY_Level_Up_Package___Level_20",
    "FREEFIRE_SGMY_Level_Up_Package___Level_25",
    "FREEFIRE_SGMY_Level_Up_Package___Level_30"
]

# ──────────────────────────────
# DEFAULT PRICES (LKR ONLY) - Used when database is empty
# ──────────────────────────────

# Default Admin Prices
DEFAULT_ADMIN_PRICES = {
    # Memberships (SG MY)
    "FREEFIRE_SGMY_WeeklyLite": 100,
    "FREEFIRE_SGMY_Weekly": 500,
    "UNGS_FFSG_Monthly": 2600,
    
    # Diamond Packs (SG MY)
    "FREEFIRE_SGMY_25": 85,
    "FREEFIRE_SGMY_100": 300,
    "FREEFIRE_SGMY_310": 950,
    "FREEFIRE_SGMY_520": 1450,
    "FREEFIRE_SGMY_1060": 2800,
    "FREEFIRE_SGMY_2180": 5500,
    "FREEFIRE_SGMY_5600": 13200,
    "FREEFIRE_SGMY_11500": 26500,
    
    # Level Up Packages
    "FREEFIRE_SGMY_Level_Up_Package___Level_6": 100,
    "FREEFIRE_SGMY_Level_Up_Package___Level_10": 220,
    "FREEFIRE_SGMY_Level_Up_Package___Level_15": 220,
    "FREEFIRE_SGMY_Level_Up_Package___Level_20": 220,
    "FREEFIRE_SGMY_Level_Up_Package___Level_25": 250,
    "FREEFIRE_SGMY_Level_Up_Package___Level_30": 290
}

# Default Customer Prices
DEFAULT_CUSTOMER_PRICES = {
    # Memberships (SG MY)
    "FREEFIRE_SGMY_WeeklyLite": 135,
    "FREEFIRE_SGMY_Weekly": 575,
    "UNGS_FFSG_Monthly": 2750,
    
    # Diamond Packs (SG MY)
    "FREEFIRE_SGMY_25": 120,
    "FREEFIRE_SGMY_100": 350,
    "FREEFIRE_SGMY_310": 1050,
    "FREEFIRE_SGMY_520": 1600,
    "FREEFIRE_SGMY_1060": 3100,
    "FREEFIRE_SGMY_2180": 6200,
    "FREEFIRE_SGMY_5600": 14500,
    "FREEFIRE_SGMY_11500": 28000,
    
    # Level Up Packages (Customer Prices)
    "FREEFIRE_SGMY_Level_Up_Package___Level_6": 110,
    "FREEFIRE_SGMY_Level_Up_Package___Level_10": 250,
    "FREEFIRE_SGMY_Level_Up_Package___Level_15": 250,
    "FREEFIRE_SGMY_Level_Up_Package___Level_20": 250,
    "FREEFIRE_SGMY_Level_Up_Package___Level_25": 280,
    "FREEFIRE_SGMY_Level_Up_Package___Level_30": 330
}

# Product display names
PRODUCT_DISPLAY_NAMES = {
    # SG MY Products
    "FREEFIRE_SGMY_WeeklyLite": "Weekly Lite",
    "FREEFIRE_SGMY_Weekly": "Weekly Membership",
    "UNGS_FFSG_Monthly": "Monthly Membership",
    "FREEFIRE_SGMY_25": "25",
    "FREEFIRE_SGMY_100": "100",
    "FREEFIRE_SGMY_310": "310",
    "FREEFIRE_SGMY_520": "520",
    "FREEFIRE_SGMY_1060": "1060",
    "FREEFIRE_SGMY_2180": "2180",
    "FREEFIRE_SGMY_5600": "5600",
    "FREEFIRE_SGMY_11500": "11500",
    
    # Level Up Packages
    "FREEFIRE_SGMY_Level_Up_Package___Level_6": "Level 6",
    "FREEFIRE_SGMY_Level_Up_Package___Level_10": "Level 10",
    "FREEFIRE_SGMY_Level_Up_Package___Level_15": "Level 15",
    "FREEFIRE_SGMY_Level_Up_Package___Level_20": "Level 20",
    "FREEFIRE_SGMY_Level_Up_Package___Level_25": "Level 25",
    "FREEFIRE_SGMY_Level_Up_Package___Level_30": "Level 30"
}

# Product codes for /id command (short codes)
PRODUCT_CODE_SHORT = {
    # SG MY Products
    "weekly": "FREEFIRE_SGMY_Weekly",
    "lite": "FREEFIRE_SGMY_WeeklyLite",
    "monthly": "UNGS_FFSG_Monthly",
    "25": "FREEFIRE_SGMY_25",
    "100": "FREEFIRE_SGMY_100",
    "310": "FREEFIRE_SGMY_310",
    "520": "FREEFIRE_SGMY_520",
    "1060": "FREEFIRE_SGMY_1060",
    "2180": "FREEFIRE_SGMY_2180",
    "5600": "FREEFIRE_SGMY_5600",
    "11500": "FREEFIRE_SGMY_11500",
    
    # Level Up Packages
    "level6": "FREEFIRE_SGMY_Level_Up_Package___Level_6",
    "level10": "FREEFIRE_SGMY_Level_Up_Package___Level_10",
    "level15": "FREEFIRE_SGMY_Level_Up_Package___Level_15",
    "level20": "FREEFIRE_SGMY_Level_Up_Package___Level_20",
    "level25": "FREEFIRE_SGMY_Level_Up_Package___Level_25",
    "level30": "FREEFIRE_SGMY_Level_Up_Package___Level_30"
}

class ProductManager:
    """Manage products from Bay2Game API"""
    
    def __init__(self):
        self.api_url = BAY2GAME_API_URL
        self.api_key = BAY2GAME_API_KEY
        self.allowed_products = ALLOWED_PRODUCTS
        self.default_admin_prices = DEFAULT_ADMIN_PRICES
        self.default_customer_prices = DEFAULT_CUSTOMER_PRICES
        self.display_names = PRODUCT_DISPLAY_NAMES
        self.short_codes = PRODUCT_CODE_SHORT
        self.cache = {
            "products": None,
            "last_updated": None
        }
        self.cache_duration = 300  # 5 minutes cache
        self._price_cache = {
            "admin": {},
            "customer": {},
            "last_updated": None
        }
        self.price_cache_duration = 60  # 1 minute cache for prices
    
    def _get_admin_prices_from_db(self) -> dict:
        """Get admin prices from database"""
        try:
            from database import db
            return db.get_all_admin_prices()
        except Exception as e:
            logger.warning(f"Could not get admin prices from database: {e}, using defaults")
            return {}
    
    def _get_customer_prices_from_db(self) -> dict:
        """Get customer prices from database"""
        try:
            from database import db
            return db.get_all_customer_prices()
        except Exception as e:
            logger.warning(f"Could not get customer prices from database: {e}, using defaults")
            return {}
    
    def _get_prices_from_db(self, is_admin: bool) -> dict:
        """Get prices from database with caching"""
        # Check cache
        if self._price_cache["last_updated"]:
            cache_age = (datetime.now() - self._price_cache["last_updated"]).total_seconds()
            if cache_age < self.price_cache_duration:
                if is_admin:
                    return self._price_cache.get("admin", {})
                else:
                    return self._price_cache.get("customer", {})
        
        # Fetch from database
        if is_admin:
            db_prices = self._get_admin_prices_from_db()
        else:
            db_prices = self._get_customer_prices_from_db()
        
        # Merge with defaults (database prices override defaults)
        if is_admin:
            default_prices = self.default_admin_prices.copy()
        else:
            default_prices = self.default_customer_prices.copy()
        
        # Update defaults with database prices
        default_prices.update(db_prices)
        
        # Update cache
        self._price_cache["admin"] = self._get_admin_prices_from_db() if is_admin else self._price_cache.get("admin", {})
        self._price_cache["customer"] = self._get_customer_prices_from_db() if not is_admin else self._price_cache.get("customer", {})
        self._price_cache["last_updated"] = datetime.now()
        
        return default_prices
    
    def get_product_price(self, product_code: str, user_id: int) -> float:
        """
        Get product price based on user role from database
        
        Args:
            product_code: Product code
            user_id: Telegram user ID
        
        Returns:
            Price in LKR
        """
        try:
            from database import db
            
            # Check if user is admin
            user = db.get_user(user_id)
            is_admin = user.get("isAdmin", False) if user else False
            
            # Get price from database
            if is_admin:
                price = db.get_admin_price(product_code)
                # If not found in database, use default
                if price == 0:
                    price = self.default_admin_prices.get(product_code, 0)
                return price
            else:
                price = db.get_customer_price(product_code)
                if price == 0:
                    price = self.default_customer_prices.get(product_code, 0)
                return price
                
        except Exception as e:
            logger.warning(f"Could not get price from database: {e}, using defaults")
            # Fallback to defaults
            return self.default_admin_prices.get(product_code, 0)
    
    def get_product_display_name(self, product_code: str) -> str:
        """Get display name for product"""
        return self.display_names.get(product_code, product_code)
    
    def get_product_code_from_short(self, short_code: str) -> Optional[str]:
        """Get full product code from short code"""
        return self.short_codes.get(short_code.lower())
    
    async def fetch_products(self, game_code: str = "freefire_sg") -> Dict:
        """
        Fetch products from Bay2Game API (only for product IDs and status)
        
        Args:
            game_code: Game code (default: freefire_sg)
        
        Returns:
            Dict containing game info and products
        """
        try:
            url = f"{self.api_url}?api_key={self.api_key}&game_code={game_code}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "success":
                    return data
                else:
                    logger.error(f"API returned error: {data}")
                    return {"status": "error", "message": "Failed to fetch products"}
                    
        except httpx.TimeoutException:
            logger.error("API request timeout")
            return {"status": "error", "message": "API request timeout"}
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            return {"status": "error", "message": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            return {"status": "error", "message": f"Error: {str(e)}"}
    
    def is_product_allowed(self, product_code: str) -> bool:
        """
        Check if product is in allowed list
        
        Args:
            product_code: Product code from API
        
        Returns:
            True if allowed, False otherwise
        """
        return product_code in self.allowed_products
    
    def format_products(self, api_response: Dict, user_id: int = None) -> Dict:
        """
        Format products from API response - filter only allowed products
        
        Args:
            api_response: Raw API response
            user_id: User ID for price calculation
        
        Returns:
            Formatted products with prices (filtered)
        """
        if api_response.get("status") != "success":
            return {
                "status": "error",
                "game": None,
                "products": [],
                "message": api_response.get("message", "Failed to fetch products")
            }
        
        game_data = api_response.get("game", {})
        products_raw = api_response.get("products", [])
        
        formatted_products = []
        skipped_products = []
        
        for product in products_raw:
            product_code = product.get("product_code", "")
            
            # Only include allowed products
            if not self.is_product_allowed(product_code):
                skipped_products.append(product_code)
                continue
            
            # Get price based on user role from database
            if user_id:
                price_lkr = self.get_product_price(product_code, user_id)
            else:
                # Default to customer price if no user_id
                price_lkr = self.default_customer_prices.get(product_code, 0)
            
            # Get display name
            display_name = self.get_product_display_name(product_code)
            
            formatted_products.append({
                "id": product.get("id"),
                "product_code": product_code,
                "name": display_name,
                "sell_price_lkr": price_lkr,
                "display_price": f"Rs. {price_lkr:,.0f}",
                "status": product.get("status"),
                "supplier_type": product.get("supplier_type"),
                "raw": product  # Keep raw data for reference
            })
        
        logger.info(f"✅ Allowed products: {len(formatted_products)}")
        logger.info(f"⏭️ Skipped products: {len(skipped_products)}")
        
        # Sort products by price (low to high)
        formatted_products.sort(key=lambda x: x.get("sell_price_lkr", 0))
        
        # Get user role for display
        user_role = "Admin" if user_id and self._is_user_admin(user_id) else "Customer"
        
        return {
            "status": "success",
            "game": {
                "game_code": game_data.get("game_code"),
                "name": game_data.get("name"),
                "description": game_data.get("description"),
                "image_url": game_data.get("image_url"),
                "fields": game_data.get("game_fields", [])
            },
            "products": formatted_products,
            "total_products": len(formatted_products),
            "skipped_products": skipped_products,
            "user_role": user_role
        }
    
    def _is_user_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        try:
            from database import db
            user = db.get_user(user_id)
            return user.get("isAdmin", False) if user else False
        except:
            return False
    
    async def get_products(self, game_code: str = "freefire_sg", user_id: int = None, force_refresh: bool = False) -> Dict:
        """
        Get products with caching - only allowed products
        
        Args:
            game_code: Game code
            user_id: User ID for price calculation
            force_refresh: Force refresh cache
        
        Returns:
            Formatted products with prices (filtered)
        """
        # Check cache
        if not force_refresh and self.cache["products"] is not None and self.cache["last_updated"]:
            cache_age = (datetime.now() - self.cache["last_updated"]).total_seconds()
            if cache_age < self.cache_duration:
                logger.info("Returning cached products")
                return self.cache["products"]
        
        # Fetch from API
        logger.info(f"Fetching products for game: {game_code}")
        api_response = await self.fetch_products(game_code)
        formatted = self.format_products(api_response, user_id)
        
        # Update cache
        if formatted.get("status") == "success":
            self.cache["products"] = formatted
            self.cache["last_updated"] = datetime.now()
        
        return formatted
    
    def get_product_by_id(self, product_id: int, user_id: int = None) -> Optional[Dict]:
        """Get product by ID from cache with user-specific price"""
        products_data = self.cache["products"]
        if not products_data:
            return None
        
        products = products_data.get("products", [])
        for product in products:
            if product.get("id") == product_id:
                # If user_id provided, update price based on role from database
                if user_id:
                    product_code = product.get("product_code")
                    price_lkr = self.get_product_price(product_code, user_id)
                    product["sell_price_lkr"] = price_lkr
                    product["display_price"] = f"Rs. {price_lkr:,.0f}"
                return product
        return None
    
    def get_product_by_code(self, product_code: str, user_id: int = None) -> Optional[Dict]:
        """Get product by product code from cache with user-specific price"""
        products_data = self.cache["products"]
        if not products_data:
            return None
        
        products = products_data.get("products", [])
        for product in products:
            if product.get("product_code") == product_code:
                # If user_id provided, update price based on role from database
                if user_id:
                    price_lkr = self.get_product_price(product_code, user_id)
                    product["sell_price_lkr"] = price_lkr
                    product["display_price"] = f"Rs. {price_lkr:,.0f}"
                return product
        return None
    
    def search_products(self, query: str) -> List[Dict]:
        """Search products by name or code"""
        products_data = self.cache["products"]
        if not products_data:
            return []
        
        products = products_data.get("products", [])
        query_lower = query.lower()
        
        results = []
        for product in products:
            if (query_lower in product.get("name", "").lower() or 
                query_lower in product.get("product_code", "").lower()):
                results.append(product)
        
        return results
    
    def get_products_by_price_range(self, min_price: float, max_price: float) -> List[Dict]:
        """Get products within price range (LKR)"""
        products_data = self.cache["products"]
        if not products_data:
            return []
        
        products = products_data.get("products", [])
        
        results = []
        for product in products:
            price = product.get("sell_price_lkr", 0)
            if min_price <= price <= max_price:
                results.append(product)
        
        return results
    
    def get_active_products(self) -> List[Dict]:
        """Get only active products"""
        products_data = self.cache["products"]
        if not products_data:
            return []
        
        products = products_data.get("products", [])
        return [p for p in products if p.get("status") == "active"]
    
    def refresh_prices(self) -> None:
        """Force refresh price cache"""
        self._price_cache["last_updated"] = None

# ──────────────────────────────
# Singleton instance
# ──────────────────────────────

product_manager = ProductManager()

# ──────────────────────────────
# Utility Functions (for bot use)
# ──────────────────────────────

async def get_game_products(game_code: str = "freefire_sg", user_id: int = None) -> Dict:
    """Get products for a specific game with user-specific prices"""
    return await product_manager.get_products(game_code, user_id)

async def get_freefire_products(user_id: int = None) -> Dict:
    """Get FreeFire SG products specifically (filtered) with user-specific prices"""
    return await product_manager.get_products("freefire_sg", user_id)

def format_products_for_display(products_data: Dict, limit: int = 20) -> str:
    """
    Format products for display in Telegram
    
    Args:
        products_data: Formatted products data
        limit: Maximum products to display
    
    Returns:
        Formatted string for display
    """
    if products_data.get("status") != "success":
        return "❌ Failed to load products. Please try again."
    
    game = products_data.get("game", {})
    products = products_data.get("products", [])
    user_role = products_data.get("user_role", "Customer")
    
    if not products:
        return "📦 No products available for this game."
    
    text = f"🎮 **{game.get('name', 'Game')} Products**\n"
    text += f"👤 Role: {user_role}\n"
    text += f"📊 Total: {len(products)} products\n\n"
    
    # Separate products
    diamond_products = []
    membership_products = []
    
    for product in products:
        name = product.get('name', '').lower()
        if 'weekly' in name or 'monthly' in name or 'membership' in name:
            membership_products.append(product)
        else:
            diamond_products.append(product)
    
    # Membership products
    if membership_products:
        text += "🔹 *Subscriptions*\n"
        for p in membership_products:
            name = p.get('name', 'Unknown')
            price = p.get('sell_price_lkr', 0)
            text += f"- {name} ⇒ `{price:.0f}` LKR\n"
        text += "\n"
    
    # Diamond products
    if diamond_products:
        text += "🔹 *Diamond Packages*\n"
        for p in diamond_products[:limit]:
            name = p.get('name', 'Unknown')
            price = p.get('sell_price_lkr', 0)
            text += f"- {name} ⇒ `{price:.0f}` LKR\n"
    
    text += "\n━━━━━━━━━━━━━━━\n"
    text += "✅ Easy | Fast | Secure\n"
    text += "📌 Example: /id 4507576164 25 2"
    
    return text

def format_product_for_inline_button(product: Dict) -> str:
    """
    Format product for inline button text
    """
    name = product.get('name', 'Unknown')
    price = product.get('sell_price_lkr', 0)
    return f"{name} - Rs. {price:,.0f}"

def create_product_keyboard(products_data: Dict, max_buttons: int = 10) -> List[List]:
    """
    Create inline keyboard from products
    
    Args:
        products_data: Formatted products data
        max_buttons: Maximum buttons per page
    
    Returns:
        List of InlineKeyboardButton rows
    """
    from telegram import InlineKeyboardButton
    
    if products_data.get("status") != "success":
        return []
    
    products = products_data.get("products", [])
    
    keyboard = []
    for product in products[:max_buttons]:
        button_text = format_product_for_inline_button(product)
        callback_data = f"buy_product_{product.get('id')}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    return keyboard

# ──────────────────────────────
# Test function (for development)
# ──────────────────────────────

async def test_products():
    """Test function to fetch and display products"""
    print("=" * 50)
    print("🔄 Testing Products with Role-Based Pricing")
    print("=" * 50)
    
    # Test as Customer (no user_id)
    print("\n📋 Customer Prices (from database):")
    customer_result = await get_freefire_products()
    
    if customer_result.get("status") == "success":
        products = customer_result.get("products", [])
        print(f"\n✅ Role: {customer_result.get('user_role', 'Customer')}")
        print(f"📊 Total Products: {len(products)}")
        print("\n📦 Products:")
        for product in products:
            print(f"\n├ {product.get('name')}")
            print(f"├ Price: Rs. {product.get('sell_price_lkr', 0):,.0f}")
            print(f"└ Code: {product.get('product_code')}")
    
    print("\n" + "=" * 50)
    
    # Try to get a specific product price
    print("\n🔍 Testing get_product_price:")
    try:
        from database import db
        # Get a test user (first user from database)
        test_user = db.users.find_one({})
        if test_user:
            user_id = test_user.get("userId")
            is_admin = test_user.get("isAdmin", False)
            price = product_manager.get_product_price("FREEFIRE_SG_25", user_id)
            print(f"├ User ID: {user_id}")
            print(f"├ Is Admin: {is_admin}")
            print(f"└ Price for FREEFIRE_SG_25: Rs. {price:,.0f}")
        else:
            print("No users found in database")
    except Exception as e:
        print(f"Error: {e}")

# ──────────────────────────────
# Main (for testing)
# ──────────────────────────────

if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_products())
