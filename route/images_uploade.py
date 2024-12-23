from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
import os
from PIL import Image
import torch
from yolov5 import YOLOv5
import pathlib
import base64

# 경로 클래스 호환성 문제 해결
pathlib.PosixPath = pathlib.WindowsPath

image_upload_bp = Blueprint('image_upload', __name__)

uploads_folder = os.path.join(os.path.dirname(__file__), '..', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

model_path = './runs/best.pt'  # 모델 파일 경로
model = YOLOv5(model_path)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_image_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


@image_upload_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(uploads_folder, filename)
        if not os.path.exists(uploads_folder):
            os.makedirs(uploads_folder)
        file.save(filepath)

        # YOLOv5 모델을 사용한 탐지
        img = Image.open(filepath)
        results = model.predict(img)
        detected_img = results.render()[0]
        detected_img = Image.fromarray(detected_img)
        save_path = os.path.join(uploads_folder, 'detected_' + filename)
        detected_img.save(save_path)

        # 라벨만 텍스트 파일에 저장
        labels = results.names
        detections = results.pred[0]
        text_save_path = os.path.join(uploads_folder, 'detection_results.txt')
        with open(text_save_path, 'w') as f:
            for *xyxy, conf, cls in detections:
                label = labels[int(cls)]
                f.write(f'{label}\n')

        # 텍스트 파일의 내용을 읽어옴
        with open(text_save_path, 'r') as f:
            text_content = f.read()

        # Base64 인코딩된 이미지를 반환
        image_base64 = get_image_base64(save_path)

        return jsonify({
            'message': 'File successfully uploaded and detected',
            'image': image_base64,
            'text': text_content
        }), 200
    else:
        return jsonify({'message': 'File type not allowed'}), 400


@image_upload_bp.route('/files', methods=['GET'])
def list_files():
    files = os.listdir(uploads_folder)
    return jsonify({'files': files}), 200
