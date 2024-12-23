import base64
from flask import Blueprint, jsonify, request
import os
from PIL import Image, ImageDraw, ImageFont
from werkzeug.utils import secure_filename
import torch
from pathlib import Path
import sys
import numpy as np

# Add the missing functions
def scale_coords(img1_shape, coords, img0_shape, ratio_pad=None):
    if ratio_pad is None:  # calculate from img0_shape
        gain = max(img1_shape) / max(img0_shape)  # gain  = old / new
        pad = (img1_shape[1] - img0_shape[1] * gain) / 2, (img1_shape[0] - img0_shape[0] * gain) / 2  # wh padding
    else:
        gain = ratio_pad[0][0]
        pad = ratio_pad[1]

    coords[:, [0, 2]] -= pad[0]  # x padding
    coords[:, [1, 3]] -= pad[1]  # y padding
    coords[:, :4] /= gain
    coords = np.clip(coords, 0, img0_shape[:2][::-1])  # clip to image size
    return coords

def select_device(device='', batch_size=None):
    s = f'YOLOv5 🚀 torch {torch.__version__} '  # string
    cpu = device.lower() == 'cpu'
    if cpu:
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # force torch.cuda.is_available() = False
    elif device:  # non-cpu device requested
        os.environ['CUDA_VISIBLE_DEVICES'] = device  # set environment variable
        assert torch.cuda.is_available(), f'CUDA unavailable, invalid device {device} requested'  # check availability

    cuda = not cpu and torch.cuda.is_available()
    if cuda:
        devices = device.split(',') if device else '0'  # range(torch.cuda.device_count())
        n = len(devices)  # device count
        if n > 1 and batch_size:  # check batch_size is divisible by device_count
            assert batch_size % n == 0, f'batch-size {batch_size} not multiple of GPU count {n}'
        space = ' ' * (len(s) + 1)
        for i, d in enumerate(devices):
            p = torch.cuda.get_device_properties(i)
            s += f"{'' if i == 0 else space}CUDA:{d} ({p.name}, {p.total_memory / 1024 ** 2:.0f}MB)\n"
    else:
        s += 'CPU\n'

    print(s)  # skip a line
    return torch.device('cuda:0' if cuda else 'cpu')

def plot_one_box(x, im, color=None, label=None, line_thickness=None):
    # Plots one bounding box on image `im` using OpenCV
    tl = line_thickness or round(0.002 * max(im.size))  # line/font thickness
    color = color or [random.randint(0, 255) for _ in range(3)]
    if isinstance(x, torch.Tensor):
        x = x.tolist()
    draw = ImageDraw.Draw(im)
    draw.rectangle([x[0], x[1], x[2], x[3]], width=tl, outline=tuple(color))
    if label:
        font = ImageFont.load_default()
        text_size = font.getsize(label)
        draw.rectangle([x[0], x[1] - text_size[1], x[0] + text_size[0], x[1]], fill=tuple(color))
        draw.text((x[0], x[1] - text_size[1]), label, fill=(255, 255, 255), font=font)

image_uploade_bp = Blueprint('image_uploade', __name__)

uploads_folder = os.path.join(os.path.dirname(__file__), 'uploads')
results_folder = os.path.join(os.path.dirname(__file__), 'results')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# YOLOv5 모델 경로 설정
yolov5_dir = Path(__file__).parent.parent / 'yolov5'
model_path = Path(__file__).parent.parent / 'runs' / 'best.pt'

# 캐시 경로 설정
os.environ['TORCH_HOME'] = str(Path.home() / '.cache' / 'torch' / 'hub')

# 경로 확인
print(f"YOLOv5 Directory: {yolov5_dir}")
print(f"Model Path: {model_path}")
print(f"TORCH_HOME: {os.environ['TORCH_HOME']}")

# YOLOv5 디렉토리를 sys.path에 추가
sys.path.insert(0, str(yolov5_dir))

# 필요한 모듈 임포트
try:
    from models.common import DetectMultiBackend
    from utils.general import non_max_suppression, LOGGER
    # from utils.datasets import LoadImages  # 이 줄을 주석 처리
    # from utils.plots import plot_one_box  # 직접 정의된 plot_one_box 함수 사용
except ImportError as e:
    print(f"Error importing YOLOv5 modules: {e}")

# 글로벌 변수 선언
model = None

# YOLOv5 모델 로드
def load_model():
    global model
    if yolov5_dir.exists() and model_path.exists():
        try:
            device = select_device('')
            model = DetectMultiBackend(weights=str(model_path), device=device)
            print("Model loaded successfully")
        except Exception as e:
            print(f"Error loading model: {e}")
            model = None
    else:
        raise FileNotFoundError(f"Model directory or model file not found: {yolov5_dir}, {model_path}")

load_model()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def resize_image(image_path, output_size=(416, 416)):
    with Image.open(image_path) as img:
        img = img.resize(output_size)
        img.save(image_path)

@image_uploade_bp.route('/imgupload', methods=['POST'])
def upload_file():
    try:
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

            print(f"File saved to {filepath}")

            # Resize image
            resize_image(filepath)
            print(f"Image resized: {filepath}")

            # Perform object detection
            global model
            if model is None:
                load_model()
            if model is not None:
                # dataset = LoadImages(filepath, img_size=640, stride=32)  # 이 줄을 주석 처리
                im = Image.open(filepath).convert("RGB")
                img = np.array(im)
                img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, to 3x416x416
                img = np.ascontiguousarray(img)

                img = torch.from_numpy(img).to(model.device)
                img = img.float()  # uint8 to fp16/32
                img /= 255.0  # 0 - 255 to 0.0 - 1.0
                if img.ndimension() == 3:
                    img = img.unsqueeze(0)

                pred = model(img, augment=False, visualize=False)
                pred = non_max_suppression(pred, 0.25, 0.45, classes=None, agnostic=False)

                im0 = im.copy()
                for i, det in enumerate(pred):
                    if len(det):
                        det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()
                        for *xyxy, conf, cls in det:
                            label = f'{model.names[int(cls)]} {conf:.2f}'
                            plot_one_box(xyxy, im0, label=label, color=(255, 0, 0), line_thickness=3)

                save_path = str(Path(results_folder) / Path(filepath).name)
                im0.save(save_path)

                # Read the image with detections and encode it to base64
                detected_image_path = Path(results_folder) / filename
                with open(detected_image_path, 'rb') as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

                return jsonify({'message': 'File successfully uploaded, resized, and processed', 'image': encoded_string}), 200
            else:
                return jsonify({'message': 'Model could not be loaded'}), 500
        else:
            return jsonify({'message': 'File type not allowed'}), 400
    except Exception as e:
        print(f"Error during file upload: {e}")
        return jsonify({'message': f'Error processing image: {e}'}), 500

@image_uploade_bp.route('/files', methods=['GET'])
def list_files():
    files = os.listdir(uploads_folder)
    return jsonify({'files': files}), 200
