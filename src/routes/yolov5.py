from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
import os
from PIL import Image
import torch
from yolov5 import YOLOv5
import pathlib
import base64
from config.yolo_settings import UPLOADS_FOLDER
from utils.yolo_file_utils import allowed_file, get_image_base64
from models.yolo_detector import YoloDetector

# 경로 클래스 호환성 문제 해결
pathlib.PosixPath = pathlib.WindowsPath

yolov5 = Blueprint('yolov5', __name__)

detector = YoloDetector()


@yolov5.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']

    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # 업로드 폴더 생성
        if not os.path.exists(UPLOADS_FOLDER):
            os.makedirs(upload_file)

        # 파일저장
        filepath = os.path.join(UPLOADS_FOLDER, filename)
        file.save(filepath)



        # YOLOv5 모델 탐지 수행
        results = detector.detect(filepath)

        #탐지된 이미지 저장
        detected_filename = 'defected_' + filename

        # 라벨 추출
        detected_labels = detector.get_detected_labels(results)

        # Base64 인코딩된 이미지를 반환
        image_base64 = get_image_base64(detected_filename)

        return jsonify({
            'message': 'File successfully uploaded and detected',
            'image': image_base64,
            'text': detected_labels
        }), 200
    else:
        return jsonify({'message': 'File type not allowed'}), 400


@yolov5.route('/files', methods=['GET'])
def list_files():
    files = os.listdir(UPLOADS_FOLDER)
    return jsonify({'files': files}), 200
