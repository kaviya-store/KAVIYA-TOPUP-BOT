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
DEFAULT_USD_TO_LKR_RATE = 349.69  # Default USD to LKR conversion rate

# Allowed products - only these will be shown
ALLOWED_PRODUCTS = [
    "FREEFIRE_SG_25",
    "FREEFIRE_SG_100",
    "FREEFIRE_SG_310",
    "FREEFIRE_SG_520",
    "FREEFIRE_SG_1060",
    "FREEFIRE_SG_2180",
    "FREEFIRE_SG_5600",
    "FREEFIRE_SG_11500",
    "FREEFIRE_SG_Weekly_Lite",
    "FREEFIRE_SG_Weekly_Membership",
    "FREEFIRE_SG_Monthly_Membership"
]

class ProductManager:
    """Manage products from Bay2Game API"""
    
    def __init__(self):
        self.api_url = BAY2GAME_API_URL
        self.api_key = BAY2GAME_API_KEY
        self.default_usd_rate = DEFAULT_USD_TO_LKR_RATE
        self.allowed_products = ALLOWED_PRODUCTS
        self.cache = {
            "products": [],
            "last_updated": None
        }
        self.cache_duration = 300  # 5 minutes cache
    
    def get_usd_rate(self) -> float:
        """
        Get USD to LKR rate from database
        If not available, use default rate
        """
        try:
            from database import db
            rate = db.get_usd_to_lkr_rate()
            return rate
        except Exception as e:
            logger.warning(f"Could not get USD rate from database: {e}, using default: {self.default_usd_rate}")
            return self.default_usd_rate
    
    def convert_price_to_lkr(self, usd_price: float) -> float:
        """
        Convert USD price to LKR using database rate
        
        Args:
            usd_price: Price in USD
        
        Returns:
            Price in LKR (rounded to 2 decimal places)
        """
        rate = self.get_usd_rate()
        return round(usd_price * rate, 2)
    
    async def fetch_products(self, game_code: str = "freefire_sg") -> Dict:
        """
        Fetch products from Bay2Game API
        
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
    
    def format_products(self, api_response: Dict) -> Dict:
        """
        Format products from API response - filter only allowed products
        
        Args:
            api_response: Raw API response
        
        Returns:
            Formatted products with LKR prices (filtered)
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
        
        # Get current rate for logging
        current_rate = self.get_usd_rate()
        logger.info(f"💰 Using USD to LKR rate: {current_rate}")
        
        for product in products_raw:
            product_code = product.get("product_code", "")
            
            # Only include allowed products
            if not self.is_product_allowed(product_code):
                skipped_products.append(product_code)
                continue
            
            usd_price = product.get("sell_price", 0)
            lkr_price = self.convert_price_to_lkr(usd_price)
            
            formatted_products.append({
                "id": product.get("id"),
                "product_code": product_code,
                "name": product.get("name"),
                "sell_price_usd": usd_price,
                "sell_price_lkr": lkr_price,
                "display_price": f"${usd_price:.2f} (Rs. {lkr_price:,.2f})",
                "status": product.get("status"),
                "supplier_type": product.get("supplier_type"),
                "raw": product  # Keep raw data for reference
            })
        
        logger.info(f"✅ Allowed products: {len(formatted_products)}")
        logger.info(f"⏭️ Skipped products: {len(skipped_products)}")
        
        # Sort products by price (low to high)
        formatted_products.sort(key=lambda x: x.get("sell_price_lkr", 0))
        
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
            "usd_rate_used": self.get_usd_rate()  # Include rate used for reference
        }
    
    async def get_products(self, game_code: str = "freefire_sg", force_refresh: bool = False) -> Dict:
        """
        Get products with caching - only allowed products
        
        Args:
            game_code: Game code
            force_refresh: Force refresh cache
        
        Returns:
            Formatted products with LKR prices (filtered)
        """
        # Check cache
        if not force_refresh and self.cache["products"] and self.cache["last_updated"]:
            cache_age = (datetime.now() - self.cache["last_updated"]).total_seconds()
            if cache_age < self.cache_duration:
                logger.info("Returning cached products")
                return self.cache["products"]
        
        # Fetch from API
        logger.info(f"Fetching products for game: {game_code}")
        api_response = await self.fetch_products(game_code)
        formatted = self.format_products(api_response)
        
        # Update cache
        if formatted.get("status") == "success":
            self.cache["products"] = formatted
            self.cache["last_updated"] = datetime.now()
        
        return formatted
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """Get product by ID from cache"""
        products = self.cache["products"].get("products", [])
        for product in products:
            if product.get("id") == product_id:
                return product
        return None
    
    def get_product_by_code(self, product_code: str) -> Optional[Dict]:
        """Get product by product code from cache"""
        products = self.cache["products"].get("products", [])
        for product in products:
            if product.get("product_code") == product_code:
                return product
        return None
    
    def search_products(self, query: str) -> List[Dict]:
        """Search products by name or code"""
        products = self.cache["products"].get("products", [])
        query_lower = query.lower()
        
        results = []
        for product in products:
            if (query_lower in product.get("name", "").lower() or 
                query_lower in product.get("product_code", "").lower()):
                results.append(product)
        
        return results
    
    def get_products_by_price_range(self, min_price: float, max_price: float) -> List[Dict]:
        """Get products within price range (LKR)"""
        products = self.cache["products"].get("products", [])
        
        results = []
        for product in products:
            price = product.get("sell_price_lkr", 0)
            if min_price <= price <= max_price:
                results.append(product)
        
        return results
    
    def get_active_products(self) -> List[Dict]:
        """Get only active products"""
        products = self.cache["products"].get("products", [])
        return [p for p in products if p.get("status") == "active"]

# ──────────────────────────────
# Singleton instance
# ──────────────────────────────

product_manager = ProductManager()

# ──────────────────────────────
# Utility Functions (for bot use)
# ──────────────────────────────

async def get_game_products(game_code: str = "freefire_sg") -> Dict:
    """Get products for a specific game"""
    return await product_manager.get_products(game_code)

async def get_freefire_products() -> Dict:
    """Get FreeFire SG products specifically (filtered)"""
    return await product_manager.get_products("freefire_sg")

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
    
    if not products:
        return "📦 No products available for this game."
    
    text = f"🎮 **{game.get('name', 'Game')} Products**\n"
    text += f"📊 Total: {len(products)} products\n"
    
    # Show rate used
    rate_used = products_data.get("usd_rate_used")
    if rate_used:
        text += f"💰 Rate: 1 USD = {rate_used:.2f} LKR\n"
    
    text += f"\n"
    
    # Show first few products
    display_products = products[:limit]
    for product in display_products:
        text += (
            f"├ 🆔 {product.get('id')}\n"
            f"├ 📝 {product.get('name')}\n"
            f"├ 💰 {product.get('display_price')}\n"
            f"├ 📦 {product.get('supplier_type', 'N/A').upper()}\n"
            f"└ {'✅ Active' if product.get('status') == 'active' else '❌ Inactive'}\n\n"
        )
    
    if len(products) > limit:
        text += f"_... and {len(products) - limit} more products_"
    
    return text

def format_product_for_inline_button(product: Dict) -> str:
    """
    Format product for inline button text
    """
    name = product.get('name', 'Unknown')
    price = product.get('sell_price_lkr', 0)
    return f"{name} - Rs. {price:,.2f}"

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
    print("🔄 Fetching FreeFire products...")
    print(f"📋 Allowed Products: {len(ALLOWED_PRODUCTS)}")
    print("=" * 50)
    
    result = await get_freefire_products()
    
    if result.get("status") == "success":
        game = result.get("game")
        products = result.get("products")
        skipped = result.get("skipped_products", [])
        rate_used = result.get("usd_rate_used", "Unknown")
        
        print(f"\n✅ Game: {game.get('name')}")
        print(f"📊 Total Products Found: {len(products)}")
        print(f"⏭️ Skipped Products: {len(skipped)}")
        print(f"💰 USD to LKR Rate: {rate_used}")
        print("\n📦 Allowed Products:")
        
        for i, product in enumerate(products, 1):
            print(f"\n{i}. Product: {product.get('name')}")
            print(f"   ├ Code: {product.get('product_code')}")
            print(f"   ├ USD: ${product.get('sell_price_usd'):.2f}")
            print(f"   ├ LKR: Rs. {product.get('sell_price_lkr'):,.2f}")
            print(f"   ├ ID: {product.get('id')}")
            print(f"   └ Status: {product.get('status')}")
        
        if skipped:
            print(f"\n⏭️ Skipped Products ({len(skipped)}):")
            for code in skipped[:10]:
                print(f"   └ {code}")
            if len(skipped) > 10:
                print(f"   ... and {len(skipped) - 10} more")
    else:
        print(f"❌ Error: {result.get('message')}")

# ──────────────────────────────
# Main (for testing)
# ──────────────────────────────

if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_products())
