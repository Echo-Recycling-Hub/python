import random as rnd
from flask import Flask, jsonify, request
from flask_restful import Resource, Api
from flask_cors import CORS
import requests
import json
import geopandas as gpd
from route.routes import recommend_bp
from route.images import images_bp
from route.mise12random import mise12random_bp
from route.images_uploade import image_upload_bp
import traceback
import pandas as pd

app = Flask(__name__)
api = Api(app)
CORS(app)
app.debug = True

access_key = 'y+MUXWRZdywDBDs64HplB3XAbAYdvxWcQ54m88FRrpMBgZAm1tcqkUc8xkXrtl4eRgFiJLN2Tmi/2iJp8tQX9A=='

app.register_blueprint(recommend_bp, url_prefix='/api')
app.register_blueprint(images_bp, url_prefix='/images')
app.register_blueprint(mise12random_bp, url_prefix='/mise12random')
app.register_blueprint(image_upload_bp, url_prefix='/img')  # 올바른 Blueprint 등록

@app.route('/api/random-data')
def random_data():
    random_number = rnd.randint(0, 150)
    return jsonify({'value': random_number})

@app.route('/api/random-data1')
def random_data1():
    random_number = rnd.randint(0, 99)
    return jsonify({'value': random_number})

@app.route('/location', methods=['GET', 'POST'])
def receive_location():
    if request.method == 'POST':
        data = request.get_json()
        current_latitude = data['currentLatitude']
        current_longitude = data['currentLongitude']
        clicked_latitude = data['clickedLatitude']
        clicked_longitude = data['clickedLongitude']

        response = get_request_url(current_latitude, current_longitude, clicked_latitude, clicked_longitude)
        response_data = json.loads(response)

        unique_route_ids = extract_unique_route_ids(response_data)
        bus_routes_data = get_bus_data(unique_route_ids.values())

        return jsonify({
            'message': 'Received and processed your request.',
            'fullResponseData': response_data,
            'busRoutesData': bus_routes_data
        }), 200
    else:
        return jsonify({'error': 'Method Not Allowed'}), 405

def extract_unique_route_ids(response_data):
    unique_routes = {}
    items = response_data.get('msgBody', {}).get('itemList', [])
    for item in items:
        for path in item.get('pathList', []):
            route_nm = path.get('routeNm')
            route_id = path.get('routeId')
            if route_nm and route_id and route_nm not in unique_routes:
                unique_routes[route_nm] = route_id
    return unique_routes

def get_request_url(current_latitude, current_longitude, clicked_latitude, clicked_longitude):
    url = "http://ws.bus.go.kr/api/rest/pathinfo/getPathInfoByBusNSub"
    params = {
        'serviceKey': access_key,
        'resultType': 'json',
        'startX': current_longitude,
        'startY': current_latitude,
        'endX': clicked_longitude,
        'endY': clicked_latitude
    }
    response = requests.get(url, params=params)
    print("Raw API Response:", response.text)
    return response.text

bus_access_key = 'fesb+j8fOHKjzliPcpuavNbsf0uBz3UH5e4Fyp3hq35oMWrBXLPEtwlecJr6NZgdNVSzGERT3ORnk3hM6itlVg=='

@app.route('/bus', methods=['GET', 'POST'])
def get_bus_data(route_ids):
    bus_routes_data = {}
    for route_id in route_ids:
        url = 'http://ws.bus.go.kr/api/rest/busRouteInfo/getRoutePath'
        params = {
            'serviceKey': bus_access_key,
            'busRouteId': route_id,
            'resultType': 'json'
        }
        response = requests.get(url, params=params)
        print(f"Raw API Response1 for route_id {route_id}:", response.text)

        response_data = response.json()
        header_cd = response_data.get('msgHeader', {}).get('headerCd')
        items = response_data.get('msgBody', {}).get('itemList')

        if header_cd == '0' and items:
            bus_routes_data[route_id] = response_data

    return bus_routes_data

@app.route('/kakao', methods=['GET', 'POST'])
def receive_location1():
    if request.method == 'GET':
        return jsonify({'message': 'GET 요청을 성공적으로 처리했습니다.'}), 200
    elif request.method == 'POST':
        data = request.get_json()
        current_latitude = data['currentLatitude']
        current_longitude = data['currentLongitude']
        clicked_latitude = data['clickedLatitude']
        clicked_longitude = data['clickedLongitude']

        response = get_request_url1(current_latitude, current_longitude, clicked_latitude, clicked_longitude)

        return jsonify(
            {
                'message': f'Received current latitude: {current_latitude}, current longitude: {current_longitude}, clicked latitude: {clicked_latitude}, clicked longitude: {clicked_longitude}',
                'carRouteInfo': response}), 200
    else:
        return jsonify({'error': 'Method Not Allowed'}), 405

def get_request_url1(current_latitude, current_longitude, clicked_latitude, clicked_longitude):
    url = "https://apis-navi.kakaomobility.com/v1/directions"
    params = {
        'origin': f"{current_longitude},{current_latitude}",
        'destination': f"{clicked_longitude},{clicked_latitude}",
        'priority': "RECOMMEND",
        'roadevent': 0,
        'alternatives': False,
        'road_details': False,
        'car_type': 1,
        'car_fuel': "GASOLINE",
        'car_hipass': False,
        'summary': False
    }
    headers = {
        "Authorization": 'KakaoAK 1c1d1475bcff3988e508016fe07cd96c',
        "Content-Type": "application/json"
    }
    response = requests.get(url, params=params, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print("Error:", response.status_code)
        return None

class City(Resource):
    def get(self):
        kor = gpd.read_file('C:\\KYB\\Project\\2_WepProject\\3_React\\React_clone_test\\kyb_study\\server\\python\\seoul_EPSG5179.shp', encoding='utf-8')
        kor.rename(columns={'nm': '시군구명'}, inplace=True)
        kor_data = kor[['시군구명', 'geometry']]
        kor_geojson = kor_data.set_crs("EPSG:4326", allow_override=True).to_json()
        return jsonify(kor_geojson)

api.add_resource(City, '/city')

if __name__ == '__main__':
    try:
        print("Starting Flask server on http://localhost:5000")
        from route.mise12random import (
            fetch_air_quality_data,
            train_model,
            get_predictions,
            find_top_7_days,
            generate_maps
        )

        air_quality_data, weather_data = fetch_air_quality_data()
        air_quality_df = pd.DataFrame(air_quality_data)
        weather_df = pd.DataFrame(weather_data)
        if not air_quality_df.empty:
            model, data = train_model(air_quality_df, weather_df)
            if model and data is not None:
                predictions_df = get_predictions(model, data)
                top_7_days = find_top_7_days(predictions_df)
                print(top_7_days)
                map_paths = generate_maps(predictions_df.to_dict(orient='records'))
                print(f"Generated {len(map_paths)} map files:")
                for path in map_paths:
                    print(path)
            else:
                print("No air quality data fetched.")
        else:
            print("No air quality data available.")

        app.run(host='localhost', debug=True)
    except Exception as e:
        print("An error occurred:")
        print(str(e))
        print("Traceback:")
        traceback.print_exc()
