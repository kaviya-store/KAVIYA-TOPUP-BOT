import os
import logging
import httpx
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, List, Optional 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Import database
from database import db
from products import product_manager, get_freefire_products, format_products_for_display
from createOrder import order_manager, process_product_purchase, format_order_result
from cloudinary_upload import upload_telegram_file_to_cloudinary

# ──────────────────────────────
# Config & Logging
# ──────────────────────────────
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ──────────────────────────────
# Constants
# ──────────────────────────────

# Conversation States
WAITING_DEPOSIT_IMAGE = 1
WAITING_DEPOSIT_METHOD = 2

# Product code mapping for /topup command
PRODUCT_CODE_MAP = {
    "weekly": "FREEFIRE_SG_Weekly_Membership",
    "weekly_lite": "FREEFIRE_SG_Weekly_Lite",
    "monthly": "FREEFIRE_SG_Monthly_Membership",
    "25": "FREEFIRE_SG_25",
    "100": "FREEFIRE_SG_100",
    "310": "FREEFIRE_SG_310",
    "520": "FREEFIRE_SG_520",
    "1060": "FREEFIRE_SG_1060",
    "2180": "FREEFIRE_SG_2180",
    "5600": "FREEFIRE_SG_5600",
    "11500": "FREEFIRE_SG_11500"
}

# Game code mapping for display
GAME_CODE_DISPLAY = {
    "FREEFIRE_SG_Weekly_Membership": "weekly",
    "FREEFIRE_SG_Weekly_Lite": "lite",
    "FREEFIRE_SG_Monthly_Membership": "monthly",
    "FREEFIRE_SG_25": "25",
    "FREEFIRE_SG_100": "100",
    "FREEFIRE_SG_310": "310",
    "FREEFIRE_SG_520": "520",
    "FREEFIRE_SG_1060": "1060",
    "FREEFIRE_SG_2180": "2180",
    "FREEFIRE_SG_5600": "5600",
    "FREEFIRE_SG_11500": "11500"
}

# ──────────────────────────────
# Helper Functions
# ──────────────────────────────

def get_product_display_name(product_code: str) -> str:
    """Get display name for product code"""
    display_names = {
        "FREEFIRE_SG_Weekly_Membership": "Weekly",
        "FREEFIRE_SG_Weekly_Lite": "Weekly Lite",
        "FREEFIRE_SG_Monthly_Membership": "Monthly",
        "FREEFIRE_SG_25": "25",
        "FREEFIRE_SG_100": "100",
        "FREEFIRE_SG_310": "310",
        "FREEFIRE_SG_520": "520",
        "FREEFIRE_SG_1060": "1060",
        "FREEFIRE_SG_2180": "2180",
        "FREEFIRE_SG_5600": "5600",
        "FREEFIRE_SG_11500": "11500"
    }
    return display_names.get(product_code, product_code)

def get_product_emoji(product_code: str) -> str:
    """Get emoji for product type"""
    if "Weekly" in product_code:
        return "📅"
    elif "Monthly" in product_code:
        return "📆"
    elif "Lite" in product_code:
        return "⚡"
    else:
        return "💎"

def get_game_code(product_code: str) -> str:
    """Get short game code for display"""
    return GAME_CODE_DISPLAY.get(product_code, product_code)

# ──────────────────────────────
# Store Command - UPDATED with user_id for pricing
# ──────────────────────────────

async def store_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show products store with loading message edit"""
    loading_msg = await update.message.reply_text(
        "🔄 Loading products... Please wait."
    )
    
    user_id = update.effective_user.id
    
    # Get products with user-specific prices
    products_data = await get_freefire_products(user_id=user_id)
    
    if products_data.get("status") != "success":
        await loading_msg.edit_text(
            "❌ Failed to load products. Please try again later."
        )
        return
    
    products = products_data.get("products", [])
    if not products:
        await loading_msg.edit_text(
            "📦 No products available at the moment."
        )
        return
    
    diamond_products = []
    membership_products = []
    
    for product in products:
        name = product.get('name', '').lower()
        if 'weekly' in name or 'monthly' in name or 'membership' in name:
            membership_products.append(product)
        else:
            diamond_products.append(product)
    
    diamond_products.sort(key=lambda x: x.get('sell_price_lkr', 0))
    membership_products.sort(key=lambda x: x.get('sell_price_lkr', 0))
    
    # Get user role
    user_role = products_data.get("user_role", "Customer")
    
    text = "✨ 𝐀𝐝𝐦𝐢𝐧 𝐊𝐚𝐯𝐢𝐲𝐚 𝐈𝐝 𝐓𝐨𝐩 𝐔𝐩 𝐂𝐞𝐧𝐭𝐞𝐫💎✨\n"
    text += f"👤 Role: {user_role}\n"
    text += "━━━━━━━━━━━━━━━\n\n"
    
    if membership_products:
        text += "🔹 Subscriptions\n"
        for p in membership_products:
            name = p.get('name', 'Unknown')
            price = p.get('sell_price_lkr', 0)
            text += f"- {name} ⇒ {price:.0f} LKR\n"
        text += "\n"
    
    if diamond_products:
        text += "🔹 Diamond Packages\n"
        for p in diamond_products:
            name = p.get('name', 'Unknown')
            price = p.get('sell_price_lkr', 0)
            code = p.get('product_code', '')
            game_code = get_game_code(code)
            text += f"- {name} ⇒ {price:.0f} LKR\n"
    
    text += "\n━━━━━━━━━━━━━━━\n"
    text += "✅ Easy | Fast | Secure\n"
    text += "📌 Example: /id 4507576164 weekly 2"
    
    await loading_msg.edit_text(text)

# ──────────────────────────────
# Topup Command - UPDATED with user-specific prices
# ──────────────────────────────

async def topup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle topup command: /id <player_id> <product> <quantity>"""
    user_id = update.effective_user.id
    args = context.args
    
    db_user = db.get_user(user_id)
    if not db_user:
        await update.message.reply_text(
            "❌ You are not registered! Please use /start"
        )
        return
    
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Invalid format!\n\n"
            "Usage: /id 4507576164 weekly 5\n"
            "Example: /id 4507576164 weekly"
        )
        return
    
    player_id = args[0]
    product_key = args[1].lower()
    quantity = int(args[2]) if len(args) > 2 else 1
    
    if not player_id.isdigit():
        await update.message.reply_text(
            "❌ Invalid Player ID! Please enter a numeric ID."
        )
        return
    
    if quantity < 1 or quantity > 10:
        await update.message.reply_text(
            "❌ Quantity must be between 1 and 10."
        )
        return
    
    product_code = PRODUCT_CODE_MAP.get(product_key)
    if not product_code:
        for key, code in PRODUCT_CODE_MAP.items():
            if product_key in key or product_key in code.lower():
                product_code = code
                break
        
        if not product_code:
            await update.message.reply_text(
                f"❌ Unknown product: {product_key}\n\n"
                "Available products:\n"
                "├ weekly - Weekly Membership\n"
                "├ lite - Weekly Lite\n"
                "├ monthly - Monthly Membership\n"
                "├ 25 - 25 Diamonds\n"
                "├ 100 - 100 Diamonds\n"
                "├ 310 - 310 Diamonds\n"
                "├ 520 - 520 Diamonds\n"
                "├ 1060 - 1060 Diamonds\n"
                "├ 2180 - 2180 Diamonds\n"
                "├ 5600 - 5600 Diamonds\n"
                "└ 11500 - 11500 Diamonds"
            )
            return
    
    # Get product with user-specific price
    product = product_manager.get_product_by_code(product_code, user_id)
    if not product:
        products_data = await get_freefire_products(user_id)
        if products_data.get("status") == "success":
            product = product_manager.get_product_by_code(product_code, user_id)
    
    if not product:
        await update.message.reply_text(
            f"❌ Product {product_key} not available at the moment."
        )
        return
    
    price_lkr = product.get('sell_price_lkr', 0)
    total_price = price_lkr * quantity
    balance = db_user.get('balance', 0)
    
    if balance < total_price:
        await update.message.reply_text(
            f"❌ Insufficient Balance!\n\n"
            f"Required: {total_price:.0f} LKR\n"
            f"Your Balance: {balance:.0f} LKR\n"
            f"Need: {total_price - balance:.0f} LKR\n\n"
            f"Please deposit first with /deposit"
        )
        return
    
    processing_msg = await update.message.reply_text(
        "🔄 Verifying Player ID..."
    )
    
    try:
        verify_url = f"https://zanta-store.vercel.app/api/verify-ffid?playerId={player_id}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(verify_url)
            data = response.json()
            
            if not data.get("success") or not data.get("player", {}).get("verified"):
                await processing_msg.delete()
                await update.message.reply_text(
                    "❌ Player ID verification failed!\n\n"
                    "Please check the Player ID and try again."
                )
                return
            
            player_name = data["player"].get("playerName", "Unknown")
            await processing_msg.delete()
            
            context.user_data['topup_data'] = {
                'player_id': player_id,
                'player_name': player_name,
                'product_code': product_code,
                'product_name': product.get('name'),
                'quantity': quantity,
                'price': price_lkr,
                'total': total_price,
                'balance': balance
            }
            
            product_display = get_product_display_name(product_code)
            emoji = get_product_emoji(product_code)
            
            confirm_text = (
                f"┌────────────┐\n"
                f"║  User     : {player_name}\n"
                f"║  UID      : {player_id}\n"
                f"└────────────┘\n"
                f"{product_display} {emoji}   ✅ x{quantity}\n"
                f"┌────────────┐\n"
                f"║  Total   : {total_price:.0f}\n"
                f"║  Balance : {balance:.0f}\n"
                f"║  After   : {balance - total_price:.0f}\n"
                f"└────────────┘\n\n"
                f"✅ Confirm your purchase?"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data="confirm_topup"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel_topup")
                ]
            ]
            
            await update.message.reply_text(
                confirm_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except Exception as e:
        await processing_msg.delete()
        await update.message.reply_text(
            f"❌ Error verifying player ID: {str(e)}\n\n"
            "Please try again later."
        )

# ──────────────────────────────
# Confirm Topup Callback - UPDATED
# ──────────────────────────────

async def confirm_topup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and process topup"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = context.user_data.get('topup_data', {})
    
    if not data:
        await query.message.edit_text(
            "❌ Session expired. Please start again with /id"
        )
        return
    
    player_id = data.get('player_id')
    player_name = data.get('player_name')
    product_code = data.get('product_code')
    quantity = data.get('quantity')
    
    await query.message.edit_text(
        "⏳ Processing your order... Please wait."
    )
    
    success_orders = []
    failed_count = 0
    
    # Get product with user-specific price
    product_obj = product_manager.get_product_by_code(product_code, user_id)
    if not product_obj:
        await query.message.edit_text(
            "❌ Product not found. Please try again."
        )
        return
    
    product_id = product_obj.get('id')
    product_display = get_product_display_name(product_code)
    emoji = get_product_emoji(product_code)
    
    for i in range(quantity):
        result = await process_product_purchase(
            user_id=user_id,
            product_id=product_id,
            game_user_id=player_id,
            game_zone_id=None
        )
        
        if result.get("success"):
            order = result.get("order", {})
            order['quantity'] = 1
            order['playerName'] = player_name
            success_orders.append(order)
        else:
            failed_count += 1
    
    context.user_data.clear()
    
    if success_orders:
        success_text = f"{player_name}\n"
        success_text += f"{product_display} {emoji}✅ {player_id} 🆔✅"
        
        if failed_count > 0:
            success_text += f"\n\n⚠️ {failed_count} orders failed."
        
        await query.message.edit_text(success_text)
    else:
        await query.message.edit_text(
            "❌ All orders failed. Please try again later."
        )

async def cancel_topup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel topup"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    await query.message.edit_text("❌ Purchase cancelled.")

# ──────────────────────────────
# DEPOSIT COMMAND
# ──────────────────────────────

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start deposit process - Send image only"""
    user_id = update.effective_user.id
    db_user = db.get_user(user_id)
    
    if not db_user:
        await update.message.reply_text(
            "❌ You are not registered! Please use /start"
        )
        return ConversationHandler.END
    
    config = db.get_bot_config()
    min_deposit = config.get("minDeposit", 100)
    max_deposit = config.get("maxDeposit", 50000)
    
    deposit_text = (
        "╔═════════════╗\n"
        "║    💳 DEPOSIT MENU \n"
        "╚═════════════╝\n\n"
        f"💰 Minimum: {min_deposit} LKR\n"
        f"💰 Maximum: {max_deposit} LKR\n\n"
        "📋 Payment Methods:\n"
        "├ 📱 EZ Cash - 0768747350\n"
        "├ 🏦 Binance - 774894425\n\n"
        "📷 Send screenshot of your payment"
    )
    
    await update.message.reply_text(deposit_text)
    return WAITING_DEPOSIT_IMAGE

# ──────────────────────────────
# RECEIVE DEPOSIT IMAGE
# ──────────────────────────────

async def receive_deposit_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive deposit image - Show method selection"""
    user_id = update.effective_user.id
    
    # Check if it's a photo
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send a photo/screenshot of your payment!\n\n"
            "Type /cancel to stop."
        )
        return WAITING_DEPOSIT_IMAGE
    
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    
    # Upload to Cloudinary
    cloudinary_url = await upload_telegram_file_to_cloudinary(file, user_id)
    
    if cloudinary_url:
        receipt_url = cloudinary_url
        reference = f"CLOUD_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"📸 Image uploaded to Cloudinary: {receipt_url}")
    else:
        file_path = file.file_path
        receipt_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        reference = f"Photo_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.warning(f"⚠️ Cloudinary failed, using Telegram URL: {receipt_url}")
    
    # Store in context
    context.user_data['deposit_data'] = {
        'user_id': user_id,
        'receipt': receipt_url,
        'reference': reference,
        'photo_file_id': photo.file_id
    }
    
    # Show method selection
    keyboard = [
        [
            InlineKeyboardButton("💰 EZ Cash", callback_data="method_ez"),
            InlineKeyboardButton("🏦 Bank Transfer", callback_data="method_bank")
        ]
    ]
    
    await update.message.reply_photo(
        photo=photo.file_id,
        caption=f"📤 Receipt Received!\n\n"
                f"📋 Reference: {reference}\n\n"
                f"❓ Please select your payment method:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return WAITING_DEPOSIT_METHOD

# ──────────────────────────────
# METHOD SELECTION CALLBACK
# ──────────────────────────────

async def method_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle method selection and create deposit"""
    query = update.callback_query
    await query.answer()
    
    method = query.data.split('_')[1]  # ez or bank
    deposit_data = context.user_data.get('deposit_data', {})
    
    if not deposit_data:
        await query.message.edit_text(
            "❌ Session expired. Please start again with /deposit"
        )
        return
    
    user_id = deposit_data.get('user_id')
    receipt_url = deposit_data.get('receipt')
    reference = deposit_data.get('reference')
    photo_file_id = deposit_data.get('photo_file_id')
    
    # ─── Create deposit in database ───
    deposit = db.create_deposit(
        user_id=user_id,
        amount=0,  # Admin will set the amount
        receipt=receipt_url,
        reference=reference
    )
    
    db.deposits.update_one(
        {"_id": deposit["_id"]},
        {"$set": {"method": method}}
    )
    
    method_display = "EZ Cash" if method == "ez" else "Bank Transfer"
    
    success_text = (
        "╔════════════╗\n"
        "║✅ DEPOSIT REQUESTED   \n"
        "╚════════════╝\n\n"
        f"📋 Reference: {reference}\n"
        f"🆔 Deposit ID: `{str(deposit['_id'])}`\n"
        f"📱 Method: {method_display.upper()}\n\n"
        f"⏳ Your deposit is pending approval."
    )
    
    try:
        await query.message.edit_caption(caption=success_text)
    except Exception as e:
        logger.warning(f"Could not edit caption: {e}")
        await query.message.reply_text(success_text)
        try:
            await query.message.delete()
        except:
            pass
    
    # ─── Send admin notification ───
    await notify_admins(context, deposit)
    
    context.user_data.clear()
    
    return ConversationHandler.END

# ──────────────────────────────
# NOTIFY ADMINS
# ──────────────────────────────

async def notify_admins(context, deposit):
    """Notify admins about new deposit with clickable commands"""
    admins = db.users.find({"isAdmin": True})
    user = db.get_user(deposit['userId'])
    
    deposit_id = str(deposit['_id'])
    
    # ─── Main notification message ───
    text = (
        f"🔔 New Deposit Request\n\n"
        f"👤 User: {user.get('firstName', 'Unknown')}\n"
        f"📱 Method: {deposit.get('method', 'N/A').upper()}\n"
        f"📋 Reference: {deposit.get('reference', 'N/A')}\n"
        f"🆔 Deposit ID: {deposit_id}\n"
        f"📸 Receipt: {deposit.get('receipt', 'N/A')}\n\n"
        f"Commands:\n"
        f"✅ /approve {deposit_id} <amount>\n"
        f"❌ /reject {deposit_id}"
    )
    
    admin_count = 0
    admin_list = list(admins)
    logger.info(f"👥 Found {len(admin_list)} admin(s)")
    
    for admin in admin_list:
        try:
            # ─── Send main notification ───
            await context.bot.send_message(
                chat_id=admin['userId'],
                text=text
            )
            
            # ─── Send deposit ID separately (for easy copying) ───
            id_text = f"{deposit_id}"
            
            await context.bot.send_message(
                chat_id=admin['userId'],
                text=id_text
            )
            
            admin_count += 1
            logger.info(f"✅ Admin notification sent to {admin['userId']}")
        except Exception as e:
            logger.error(f"❌ Failed to notify admin {admin['userId']}: {e}")
    
    logger.info(f"📨 Deposit notification sent to {admin_count} admin(s)")

# ──────────────────────────────
# CANCEL DEPOSIT
# ──────────────────────────────

async def cancel_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel deposit"""
    context.user_data.clear()
    await update.message.reply_text("❌ Deposit cancelled.")
    return ConversationHandler.END

# ──────────────────────────────
# ADMIN APPROVE COMMAND
# ──────────────────────────────

async def approve_deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve deposit: /approve <deposit_id> <amount>"""
    user_id = update.effective_user.id
    
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ No permission! Admin only.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Usage: /approve <deposit_id> <amount>\n"
            "Example: /approve 67a8b9c0d1e2f3 500"
        )
        return
    
    deposit_id = context.args[0]
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount! Please enter a number.")
        return
    
    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive!")
        return
    
    # ─── Use the new function ───
    success, message = db.approve_deposit_with_amount(deposit_id, user_id, amount)
    
    if success:
        await update.message.reply_text(
            f"✅ {message}\n"
            f"💰 Amount: {amount:.2f} LKR\n"
            f"🆔 Deposit ID: {deposit_id}"
        )
    else:
        await update.message.reply_text(f"❌ {message}")

# ──────────────────────────────
# ADMIN REJECT COMMAND
# ──────────────────────────────

async def reject_deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject deposit: /reject <deposit_id>"""
    user_id = update.effective_user.id
    
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ No permission! Admin only.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ Usage: /reject <deposit_id>\n"
            "Example: /reject 67a8b9c0d1e2f3"
        )
        return
    
    deposit_id = context.args[0]
    success = db.reject_deposit(deposit_id, user_id)
    
    if success:
        await update.message.reply_text(
            f"✅ Deposit rejected!\n"
            f"🆔 Deposit ID: {deposit_id}"
        )
    else:
        await update.message.reply_text("❌ Failed to reject deposit. Please check the ID.")

# ──────────────────────────────
# START COMMAND
# ──────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - Register user and show welcome message"""
    user = update.effective_user
    
    phone_number = None
    if context.args and len(context.args) > 0:
        phone_number = context.args[0]
    
    db_user = db.create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    if phone_number:
        db.users.update_one(
            {"userId": user.id},
            {"$set": {"phoneNumber": phone_number}}
        )
        db_user = db.get_user(user.id)
    
    welcome_text = (
        "║💎  𝐀𝐝𝐦𝐢𝐧 𝐊𝐚𝐯𝐢𝐲𝐚 𝐈𝐝 𝐓𝐨𝐩 𝐔𝐩 𝐂𝐞𝐧𝐭𝐞𝐫  💎║\n\n"
        f"👋 Hey {user.first_name}!\n"
        "🎉 Welcome to 𝐀𝐝𝐦𝐢𝐧 𝐊𝐚𝐯𝐢𝐲𝐚 𝐈𝐝 𝐓𝐨𝐩 𝐔𝐩 𝐂𝐞𝐧𝐭𝐞𝐫!\n\n"
        "📱 Your Account Details:\n"
        f"├ 🆔 ID: {user.id}\n"
        f"├ 👤 Name: {user.first_name}\n"
        f"├ 💰 Balance: {db_user['balance']:.2f} LKR\n"
        f"├ 📦 Orders: {db_user.get('totalOrders', 0)}\n"
        f"└ 📅 Joined: {db_user['createdAt'][:10]}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📌 Available Commands:\n"
        "├ /wallet\n"
        "├ /products\n"
        "├ /id\n"
        "├ /deposit\n"
        "├ /orders\n"
        "└ /history\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 Example: /id 4507576164 weekly 2"
    )
    
    await update.message.reply_text(welcome_text)

# ──────────────────────────────
# WALLET/PROFILE COMMAND
# ──────────────────────────────

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user wallet/profile"""
    user_id = update.effective_user.id
    db_user = db.get_user(user_id)
    
    if not db_user:
        await update.message.reply_text(
            "❌ You are not registered! Please use /start"
        )
        return
    
    profile_text = (
        "╔═══════════╗\n"
        "║    👤 USER PROFILE      \n"
        "╚═══════════╝\n\n"
        f"├ 🆔 ID: {db_user['userId']}\n"
        f"├ 👤 Name: {db_user.get('firstName', 'N/A')}\n"
        f"├ 💰 Balance: {db_user['balance']:.2f} LKR\n"
        f"├ 📦 Orders: {db_user.get('totalOrders', 0)}\n"
        f"├ 💳 Deposits: {db_user.get('totalDeposits', 0)}\n"
        f"├ 📅 Joined: {db_user['createdAt'][:10]}\n"
        f"└ 🛡️ Status: {'✅ Active' if not db_user.get('isBanned', False) else '❌ Banned'}"
    )
    
    await update.message.reply_text(profile_text)

# ──────────────────────────────
# ORDERS COMMAND
# ──────────────────────────────

async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show orders history"""
    user_id = update.effective_user.id
    
    orders = db.get_user_orders(user_id, limit=20)
    
    if not orders:
        await update.message.reply_text(
            "📦 No orders found.\n\nStart shopping with /id!"
        )
        return
    
    text = "╔═══════════╗\n"
    text += "║  📦 ORDER HISTORY    \n"
    text += "╚═══════════╝\n\n"
    
    for order in orders[:10]:
        status_emoji = "✅" if order.get('status') == 'completed' else "⏳" if order.get('status') == 'pending' else "❌"
        product = order.get('productName', 'N/A')
        amount = order.get('amountLKR', 0)
        date = order.get('createdAt', 'N/A')[:10]
        
        text += f"{status_emoji} {product}\n"
        text += f"   ├ 💰 {amount:.0f} LKR\n"
        text += f"   ├ 🎯 {order.get('playerId', 'N/A')}\n"
        text += f"   └ 📅 {date}\n\n"
    
    if len(orders) > 10:
        text += f"... and {len(orders) - 10} more"
    
    await update.message.reply_text(text)

# ──────────────────────────────
# HISTORY COMMAND
# ──────────────────────────────

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deposit history"""
    user_id = update.effective_user.id
    
    deposits = db.get_user_deposits(user_id, limit=20)
    
    if not deposits:
        await update.message.reply_text(
            "📋 No deposits found.\n\nMake a deposit with /deposit!"
        )
        return
    
    pending_count = sum(1 for d in deposits if d.get('status') == 'pending')
    approved_count = sum(1 for d in deposits if d.get('status') == 'approved')
    rejected_count = sum(1 for d in deposits if d.get('status') == 'rejected')
    
    text = "╔════════════╗\n"
    text += "║   💳 DEPOSIT HISTORY    \n"
    text += "╚════════════╝\n\n"
    
    text += "📊 Summary:\n"
    text += f"├ ⏳ Pending: {pending_count}\n"
    text += f"├ ✅ Approved: {approved_count}\n"
    text += f"└ ❌ Rejected: {rejected_count}\n\n"
    
    text += "📋 Details:\n"
    for dep in deposits[:10]:
        status_emoji = "✅" if dep.get('status') == 'approved' else "⏳" if dep.get('status') == 'pending' else "❌"
        amount = dep.get('amount', 0)
        method = dep.get('method', 'N/A').upper()
        date = dep.get('createdAt', 'N/A')[:10]
        
        text += f"{status_emoji} {amount:.0f} LKR\n"
        text += f"   ├ 📱 {method}\n"
        text += f"   └ 📅 {date}\n\n"
    
    if len(deposits) > 10:
        text += f"... and {len(deposits) - 10} more"
    
    await update.message.reply_text(text)

# ──────────────────────────────
# ADD BALANCE COMMAND (Admin)
# ──────────────────────────────

async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add balance to user (admin only)"""
    user_id = update.effective_user.id
    
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ No permission!")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Usage: /addbalance <user_id> <amount>\n"
            "Example: /addbalance 123456789 500"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        amount = float(context.args[1])
        
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive!")
            return
        
        success = db.update_balance(target_user_id, amount)
        
        if success:
            user = db.get_user(target_user_id)
            await update.message.reply_text(
                f"✅ Added {amount:.2f} LKR to user {target_user_id}\n"
                f"💰 New Balance: {user['balance']:.2f} LKR"
            )
        else:
            await update.message.reply_text("❌ User not found!")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid format! Use: /addbalance <user_id> <amount>")

# ──────────────────────────────
# CALLBACK QUERY HANDLER
# ──────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries"""
    query = update.callback_query
    data = query.data
    
    if data == "confirm_topup":
        await confirm_topup_callback(update, context)
    elif data == "cancel_topup":
        await cancel_topup_callback(update, context)
    elif data.startswith("method_"):
        await method_selection_callback(update, context)
    else:
        await query.answer()
        await query.message.edit_text(
            "⚠️ Unknown option! Please use commands."
        )

# ──────────────────────────────
# MAIN
# ──────────────────────────────

def main():
    """Main function to run the bot"""
    app = ApplicationBuilder().token(TOKEN).build()
    
    # ── Deposit Conversation ──
    deposit_handler = ConversationHandler(
    entry_points=[
        CommandHandler("deposit", deposit_command),
    ],
    states={
        WAITING_DEPOSIT_IMAGE: [
            MessageHandler(
                filters.PHOTO,
                receive_deposit_image
            )
        ],
        WAITING_DEPOSIT_METHOD: [
            CallbackQueryHandler(
                method_selection_callback,
                pattern="^method_"
            )
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_deposit)
    ],
    allow_reentry=True
)
    
    # ── Command Handlers ──
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wallet", wallet_command))
    app.add_handler(CommandHandler("products", store_command))
    app.add_handler(CommandHandler("id", topup_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("deposit", deposit_command))
    
    # ── Admin Commands ──
    app.add_handler(CommandHandler("addbalance", add_balance_command))
    app.add_handler(CommandHandler("approve", approve_deposit_command))
    app.add_handler(CommandHandler("reject", reject_deposit_command))
    
    # ── Conversation Handlers ──
    app.add_handler(deposit_handler)
    
    # ── Callback Handler ──
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("=" * 50)
    print("🤖 TopUp Bot is running...")
    print("📊 MongoDB: Connected")
    print("🎮 Bay2Game API: Connected")
    print("☁️ Cloudinary: Connected")
    print(f"🔑 Bot Token: {TOKEN[:10]}...")
    print("=" * 50)
    print("✅ Bot is ready! Press Ctrl+C to stop.")
    print("=" * 50)
    print("\n📌 Available Commands:")
    print("  /wallet      - View wallet/profile")
    print("  /products    - View products")
    print("  /id          - Buy products")
    print("  /deposit     - Deposit money (send screenshot)")
    print("  /orders      - Order history")
    print("  /history     - Deposit history")
    print("  /approve     - Approve deposit (Admin)")
    print("  /reject      - Reject deposit (Admin)")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
