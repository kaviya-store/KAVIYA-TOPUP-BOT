import os
import cloudinary
import cloudinary.uploader
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ──────────────────────────────
# Cloudinary Config
# ──────────────────────────────

CLOUDINARY_CLOUD_NAME = "dqlh378fb"
CLOUDINARY_API_KEY = "762638296874182"
CLOUDINARY_API_SECRET = "TubYkMp4RRNsVyiLudssYcTVWDY"

# Configure Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

async def upload_to_cloudinary(image_data, user_id: int) -> str:
    """
    Upload image to Cloudinary and return URL
    
    Args:
        image_data: Image file data (bytes)
        user_id: Telegram user ID for naming
    
    Returns:
        Cloudinary image URL
    """
    try:
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        public_id = f"deposits/user_{user_id}_{timestamp}"
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            image_data,
            public_id=public_id,
            folder="zanta_deposits",
            resource_type="image",
            transformation=[
                {'quality': 'auto:good'},
                {'fetch_format': 'auto'}
            ]
        )
        
        image_url = result.get('secure_url')
        logger.info(f"✅ Image uploaded to Cloudinary: {image_url}")
        
        return image_url
        
    except Exception as e:
        logger.error(f"❌ Cloudinary upload error: {e}")
        return None

async def upload_telegram_file_to_cloudinary(file_obj, user_id: int) -> str:
    """
    Download Telegram file and upload to Cloudinary
    
    Args:
        file_obj: Telegram file object
        user_id: Telegram user ID
    
    Returns:
        Cloudinary image URL
    """
    try:
        # Download file as bytes
        image_data = await file_obj.download_as_bytearray()
        
        # Upload to Cloudinary
        return await upload_to_cloudinary(image_data, user_id)
        
    except Exception as e:
        logger.error(f"❌ Error processing Telegram file: {e}")
        return None
