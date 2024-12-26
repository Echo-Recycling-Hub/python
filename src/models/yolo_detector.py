from PIL import Image
from yolov5 import YOLOv5
from config.yolo_settings import MODEL_PATH

class YoloDetector:
    def __init__(self, model_path=MODEL_PATH):
        self.model = YOLOv5(model_path)

    def detect(self, image_path):
        img = Image.open(image_path)
        results = self.model.predict(img)
        return results

    def save_detection_results(self, results, save_path):
        # 탐지된 이미지 저장
        detected_img = results.render()[0]
        detected_img = Image.fromarray(detected_img)
        detected_img.save(save_path)

    def get_detected_labels(self, results):
        # 라벨 추출
        labels = results.names
        detections = results.pred[0]
        detected_labels = []
        for *xyxy, conf, cls in detections:
            label = labels[int(cls)]
            detected_labels.append(label)
        return detected_labels