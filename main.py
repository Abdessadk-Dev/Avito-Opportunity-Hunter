import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import time
import logging
from configparser import ConfigParser

# ============== تهيئة السجلات ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("avito_hunter.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AvitoHunter")

# ============== إعدادات التكوين ==============
config = ConfigParser()
config.read('config.ini')

def get_config(section, key, default=None):
    try:
        return config.get(section, key)
    except:
        return default

# ============== معايير التكوين ==============
TARGET_URL = get_config('SETTINGS', 'TARGET_URL', "https://www.avito.ma/maroc/appartements-%C3%A0_louer")
TELEGRAM_TOKEN = get_config('TELEGRAM', 'BOT_TOKEN', "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = get_config('TELEGRAM', 'CHAT_ID', "YOUR_CHAT_ID")
DB_NAME = get_config('DATABASE', 'DB_NAME', "avito_ads.db")
SCAN_INTERVAL = int(get_config('SETTINGS', 'SCAN_INTERVAL', 300))  # 5 دقائق افتراضيًا

# ============== معايير الفلترة ==============
FILTER_CRITERIA = {
    'max_price': int(get_config('FILTERS', 'MAX_PRICE', 5000)),
    'required_location': get_config('FILTERS', 'LOCATION', "Casablanca"),
    'keyword': get_config('FILTERS', 'KEYWORD', "Maarif"),
    'min_area': int(get_config('FILTERS', 'MIN_AREA', 0)),
    'min_rooms': int(get_config('FILTERS', 'MIN_ROOMS', 0))
}

# ============== مرحلة 1: استخلاص البيانات ==============
def scrape_avito(url):
    ads = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'ar,en;q=0.9',
            'Referer': 'https://www.avito.ma/'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            container = soup.find('div', class_='sc-jejop8-0')
            
            if container:
                for item in container.find_all('a', class_='sc-1jge648-0'):
                    try:
                        # استخراج العنوان
                        title_tag = item.find('div', class_='sc-1x0vz2r-0')
                        title = title_tag.get_text(strip=True) if title_tag else "N/A"
                        
                        # استخراج الرابط
                        relative_url = item.get('href', '')
                        full_url = f"https://www.avito.ma{relative_url}" if relative_url.startswith('/') else relative_url
                        
                        # استخراج السعر
                        price_tag = item.find('div', class_='sc-1x0vz2r-0')
                        price_text = price_tag.get_text(strip=True).replace('DH', '').replace(',', '') if price_tag else "0"
                        price = int(re.search(r'\d+', price_text).group()) if re.search(r'\d+', price_text) else 0
                        
                        # استخراج الموقع
                        location_tag = item.find('span', class_='sc-1x0vz2r-0')
                        location = location_tag.get_text(strip=True) if location_tag else "N/A"
                        
                        # استخراج البيانات الإضافية
                        metadata_tag = item.find('div', class_='sc-1x0vz2r-0')
                        metadata = metadata_tag.get_text(strip=True) if metadata_tag else ""
                        
                        # استخراج المساحة وعدد الغرف من الوصف
                        area, rooms = extract_features(metadata)
                        
                        ads.append({
                            'title': title,
                            'url': full_url,
                            'price': price,
                            'location': location,
                            'metadata': metadata,
                            'area': area,
                            'rooms': rooms
                        })
                    except Exception as e:
                        logger.error(f"خطأ في معالجة إعلان: {e}")
    except Exception as e:
        logger.error(f"خطأ في استخلاص البيانات: {e}")
    return ads

def extract_features(metadata):
    """استخراج المساحة وعدد الغرف من البيانات الوصفية"""
    area = 0
    rooms = 0
    
    # البحث عن المساحة
    area_match = re.search(r'(\d+)\s*m²', metadata)
    if area_match:
        area = int(area_match.group(1))
    
    # البحث عن عدد الغرف
    rooms_match = re.search(r'(\d+)\s*غرفة|(\d+)\s*pieces', metadata, re.IGNORECASE)
    if rooms_match:
        rooms = int(rooms_match.group(1) if rooms_match.group(1) else int(rooms_match.group(2))
    
    return area, rooms

# ============== مرحلة 2: معالجة وتصفية البيانات ==============
def filter_ads(ads_list):
    filtered = []
    for ad in ads_list:
        try:
            # تطبيق شروط الفلترة
            price_ok = ad['price'] <= FILTER_CRITERIA['max_price'] if ad['price'] else False
            location_ok = FILTER_CRITERIA['required_location'] in ad['location']
            keyword_ok = FILTER_CRITERIA['keyword'].lower() in ad['title'].lower()
            area_ok = ad['area'] >= FILTER_CRITERIA['min_area']
            rooms_ok = ad['rooms'] >= FILTER_CRITERIA['min_rooms']
            
            if all([price_ok, location_ok, keyword_ok, area_ok, rooms_ok]):
                filtered.append(ad)
        except Exception as e:
            logger.error(f"خطأ في تصفية الإعلان: {e}")
    return filtered

# ============== مرحلة 3: إدارة قاعدة البيانات ==============
def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS sent_ads (
                        url TEXT PRIMARY KEY,
                        title TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')
        conn.commit()
    except Exception as e:
        logger.error(f"خطأ في تهيئة قاعدة البيانات: {e}")
    finally:
        conn.close()

def is_ad_sent(url):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT 1 FROM sent_ads WHERE url=?", (url,))
        exists = c.fetchone() is not None
        return exists
    except Exception as e:
        logger.error(f"خطأ في التحقق من الإعلان: {e}")
        return True  # لمنع التكرار في حالة الخطأ
    finally:
        conn.close()

def mark_ad_sent(ad):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO sent_ads (url, title) VALUES (?, ?)", 
                 (ad['url'], ad['title']))
        conn.commit()
    except Exception as e:
        logger.error(f"خطأ في تسجيل الإعلان: {e}")
    finally:
        conn.close()

# ============== مرحلة 4: الإشعارات ==============
def send_telegram_notification(ad):
    try:
        # بناء رسالة غنية بالمعلومات
        features = []
        if ad['area'] > 0:
            features.append(f"📏 المساحة: {ad['area']}m²")
        if ad['rooms'] > 0:
            features.append(f"🚪 الغرف: {ad['rooms']}")
            
        features_text = "\n".join(features) if features else "⚠️ لا توجد معلومات إضافية"
        
        message = (
            f"🏠 **فرصة عقارية جديدة!**\n\n"
            f"📍 **{ad['title']}**\n"
            f"💰 **السعر:** {ad['price']} درهم\n"
            f"🗺️ **الموقع:** {ad['location']}\n"
            f"{features_text}\n\n"
            f"🔗 [عرض التفاصيل على أفيتو]({ad['url']})"
        )
        
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': False
        }
        
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"فشل إرسال الإشعار: {response.status_code} - {response.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"خطأ في إرسال الإشعار: {e}")
        return False

# ============== الدالة الرئيسية ==============
def main():
    init_db()
    
    logger.info("="*50)
    logger.info("بدء مراقبة أفيتو للفرص العقارية")
    logger.info(f"الرابط المستهدف: {TARGET_URL}")
    logger.info(f"الفاصل الزمني: {SCAN_INTERVAL//60} دقائق")
    logger.info(f"معايير الفلترة: السعر ≤ {FILTER_CRITERIA['max_price']} درهم")
    logger.info(f"الموقع: {FILTER_CRITERIA['required_location']}")
    logger.info(f"الكلمة المفتاحية: '{FILTER_CRITERIA['keyword']}'")
    logger.info(f"الحد الأدنى للمساحة: {FILTER_CRITERIA['min_area']}m²")
    logger.info(f"الحد الأدنى للغرف: {FILTER_CRITERIA['min_rooms']}")
    logger.info("="*50)
    
    while True:
        try:
            logger.info("جاري فحص الإعلانات الجديدة...")
            ads = scrape_avito(TARGET_URL)
            logger.info(f"تم العثور على {len(ads)} إعلان(ات)")
            
            filtered_ads = filter_ads(ads)
            logger.info(f"تمت تصفية إلى {len(filtered_ads)} إعلان(ات) مطابقة للمعايير")
            
            new_ads = 0
            for ad in filtered_ads:
                if not is_ad_sent(ad['url']):
                    logger.info(f"إعلان جديد: {ad['title']}")
                    if send_telegram_notification(ad):
                        mark_ad_sent(ad)
                        new_ads += 1
                else:
                    logger.debug(f"تم التجاوز: الإعلان مرسل سابقاً - {ad['title']}")
            
            if new_ads:
                logger.info(f"تم إرسال {new_ads} إعلان(ات) جديدة")
            else:
                logger.info("لم يتم العثور على إعلانات جديدة")
            
        except Exception as e:
            logger.error(f"خطأ غير متوقع: {e}", exc_info=True)
        
        logger.info(f"جاري الانتظار {SCAN_INTERVAL} ثانية للفحص التالي...")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
