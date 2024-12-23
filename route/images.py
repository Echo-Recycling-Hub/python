import cx_Oracle
import base64
from flask import Blueprint, jsonify
from sqlalchemy import create_engine, text

images_bp = Blueprint('images_bp', __name__)

# SQLAlchemy 엔진 생성
engine = create_engine('oracle+cx_oracle://kyb:1111@localhost:1521/xe')

@images_bp.route('/<int:index>', methods=['GET'])
def get_image(index):
    connection = None
    try:
        connection = engine.connect()
        print(f"Connected to the database. Fetching image for ID: {index}")
        # 특정 인덱스에 해당하는 이미지를 선택
        result = connection.execute(text('SELECT * FROM ZERO_IMAGES WHERE ID = :id'), {'id': index})

        row = result.fetchone()
        if not row:
            print(f"No data found for the given index: {index}")
            return jsonify({'error': 'No data found for the given index'}), 404

        image_data = {
            'id': row[0],
            'image_id': row[1],
            'img1': blob_to_base64(row[2]) if row[2] else None,
            'img2': blob_to_base64(row[3]) if row[3] else None,
            'img3': blob_to_base64(row[4]) if row[4] else None,
            'img4': blob_to_base64(row[5]) if row[5] else None,
            'img5': blob_to_base64(row[6]) if row[6] else None,
            'img6': blob_to_base64(row[7]) if row[7] else None,
            'img7': blob_to_base64(row[8]) if row[8] else None,
            'img8': blob_to_base64(row[9]) if row[9] else None
        }

        print(f"Image data for ID {index}: {image_data}")
        return jsonify(image_data)
    except Exception as e:
        print(f"An error occurred: {e}")
        return '에러남', 500
    finally:
        if connection:
            connection.close()

def blob_to_base64(blob):
    if blob is None:
        return None
    return base64.b64encode(blob).decode('utf-8')
