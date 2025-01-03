import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
UPLOADS_FOLDER = os.path.join(BASE_DIR, 'src', 'uploads')
MODEL_PATH = os.path.join(BASE_DIR, 'src', 'models', 'weights', 'best.pt')
STATION_PATH = os.path.join(BASE_DIR, 'data', 'station_info.csv')


# 파일 설정
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}