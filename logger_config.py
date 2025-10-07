import logging
import os

# Buat folder logs jika belum ada
if not os.path.exists('logs'):
    os.makedirs('logs')

# Konfigurasi logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/debug.log"),
        logging.StreamHandler()
    ]
)

# Buat logger
logger = logging.getLogger(__name__)
