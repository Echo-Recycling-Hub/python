from flask import Blueprint, jsonify, send_file
import pandas as pd
import numpy as np
import requests
import requests_cache
from sklearn.ensemble import GradientBoostingRegressor
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import folium
from folium.plugins import HeatMap
from branca.colormap import LinearColormap
import os
import time
import random
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

mise12random_bp = Blueprint('mise12random', __name__)

# 측정소 정보 데이터 로드
station_info_path = r'D:\\KYB\\Project\\2_WepProject\\3_React\\React_clone_test\\kyb_study\\server\\public\\csv\\station_info.csv'
station_info = pd.read_csv(station_info_path)

# API 호출 설정
base_url = 'http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty'
api_key = 'sDUeQTyY7AP6gn8TrVaWb%2FT%2Fn7a8%2Fxee5eRZzr4wwROd2lE0LXkL9lO4WjigWDtReH7O5dymtlpuh5qBN3MZ7w%3D%3D'
params = {
    'serviceKey': api_key,
    'returnType': 'xml',
    'numOfRows': 100,
    'pageNo': 1,
    'dataTerm': 'MONTH',
    'ver': '1.0'
}

weather_api_key = 'd3a63f8ecd92238306b3358700ba4639'  # OpenWeatherMap API 키

# Weather data cache
weather_cache = {}


# Cache 설정
# requests_cache.install_cache('air_quality_cache', backend='sqlite', expire_after=1800)

def fetch_weather_data(lat, lon, retries=3, backoff=1):
    print(f"Fetching weather data for lat: {lat}, lon: {lon}")
    cache_key = (lat, lon)
    current_time = time.time()

    # 캐시 확인 및 만료 시간 체크
    if cache_key in weather_cache:
        cached_data, timestamp = weather_cache[cache_key]
        if current_time - timestamp < 1800:  # 30분 캐시 유효 시간
            return cached_data

    weather_url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_api_key}&units=metric"
    for attempt in range(retries):
        try:
            response = requests.get(weather_url)
            if response.status_code == 200:
                data = response.json()
                temp = data['main']['temp']
                humidity = data['main']['humidity']
                wind_speed = data['wind']['speed']
                rain = data.get('rain', {}).get('1h', 0.0)
                weather_cache[cache_key] = ((temp, humidity, wind_speed, rain), current_time)
                return weather_cache[cache_key][0]
            else:
                print(f"Failed to retrieve weather data. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
    weather_cache[cache_key] = ((20.0, 50.0, 5.0, 0.0), current_time)
    return weather_cache[cache_key][0]


def fetch_station_data(station):
    print(f"Fetching station data for station: {station}")
    all_data = []
    params['stationName'] = station
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(base_url, params=params, verify=False)  # 인증서 확인 비활성화
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for item in root.findall('.//item'):
                    data_time = item.find('dataTime').text
                    if '24:00' in data_time:
                        data_time = data_time.replace('24:00', '00:00')
                        date_obj = datetime.strptime(data_time, '%Y-%m-%d %H:%M') + timedelta(days=1)
                        data_time = date_obj.strftime('%Y-%m-%d %H:%M')
                    lat = station_info.loc[station_info['stationName'] == station, 'dmX'].values[0]
                    lon = station_info.loc[station_info['stationName'] == station, 'dmY'].values[0]
                    temp, humidity, wind_speed, rain = fetch_weather_data(lat, lon)
                    data = {
                        'stationName': station,
                        'DateTime': data_time,
                        'PM10Value': item.find('pm10Value').text if item.find('pm10Value') is not None else np.nan,
                        'SO2Value': item.find('so2Value').text if item.find('so2Value') is not None else np.nan,
                        'COValue': item.find('coValue').text if item.find('coValue') is not None else np.nan,
                        'O3Value': item.find('o3Value').text if item.find('o3Value') is not None else np.nan,
                        'NO2Value': item.find('no2Value').text if item.find('no2Value') is not None else np.nan,
                        'Temperature': temp,
                        'Humidity': humidity,
                        'WindSpeed': wind_speed,
                        'Rain': rain
                    }
                    all_data.append(data)
            else:
                print(f"Failed to retrieve data for station {station}. Status code: {response.status_code}")
            break  # 요청이 성공하면 루프를 빠져나옴
        except requests.exceptions.RequestException as e:
            print(
                f"Error occurred while fetching data for station {station}. Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5)  # 5초 대기 후 다시 시도
        except ET.ParseError as e:
            print(f"Error parsing XML data for station {station}. Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5)  # 5초 대기 후 다시 시도
        except KeyError as e:
            print(f"Error accessing data for station {station}. Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5)  # 5초 대기 후 다시 시도
        except Exception as e:
            print(f"Unexpected error occurred for station {station}. Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5)  # 5초 대기 후 다시 시도
    return all_data


def fetch_air_quality_data():
    all_data = []
    weather_data = []
    print("Starting to fetch air quality data...")

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(fetch_station_data, station) for station in station_info['stationName']]

        for future in as_completed(futures):
            try:
                station_data = future.result()
                all_data.extend(station_data)
                for data in station_data:
                    weather_data.append({
                        'stationName': data['stationName'],
                        'Temperature': data['Temperature'],
                        'Humidity': data['Humidity'],
                        'WindSpeed': data['WindSpeed'],
                        'Rain': data['Rain']
                    })
                print(f"Fetched data for {len(station_data)} records from {data['stationName']}.")
            except Exception as e:
                print(f"Error fetching station data: {e}")
                traceback.print_exc()

    print(f"Total air quality records fetched: {len(all_data)}")
    return all_data, weather_data


def train_model(air_quality_df, weather_df):
    print("Training model...")
    air_quality_df.replace('-', np.nan, inplace=True)
    if not air_quality_df.empty:
        air_quality_df.columns = ['stationName', 'DateTime', 'PM10Value', 'SO2Value', 'COValue', 'O3Value', 'NO2Value',
                                  'Temperature', 'Humidity', 'WindSpeed', 'Rain']
        air_quality_df['DateTime'] = pd.to_datetime(air_quality_df['DateTime'], format='%Y-%m-%d %H:%M')
        data = pd.merge(air_quality_df, station_info, on='stationName')
        data = pd.merge(data, weather_df.drop_duplicates(subset=['stationName']), on='stationName',
                        suffixes=('', '_weather'))
        data = data.dropna(subset=['PM10Value', 'Temperature', 'Humidity', 'WindSpeed', 'Rain'])  # NaN 값이 포함된 샘플 제거
        data['PM10Value'] = data['PM10Value'].astype(float)

        print(f"Training data size: {len(data)}")

        # Include dmX, dmY, month, and hour in the model
        data['month'] = data['DateTime'].dt.month
        data['hour'] = data['DateTime'].dt.hour
        X = data[['DateTime', 'dmX', 'dmY', 'month', 'hour', 'Temperature', 'Humidity', 'WindSpeed', 'Rain']]
        X.loc[:, 'DateTime'] = X['DateTime'].map(datetime.toordinal)
        y = data['PM10Value']

        model = GradientBoostingRegressor(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42)
        model.fit(X, y)
        print("Model training completed.")
        return model, data
    print("Model training failed.")
    return None, None





def get_predictions(model, data):
    print("Generating predictions...")
    predictions = []
    last_date = data['DateTime'].max()
    print(f"Last date in the data: {last_date}")

    for day in range(1, 31):  # 한 달 동안의 예측
        future_date = last_date + timedelta(days=day)
        future_month = future_date.month
        future_hour = future_date.hour

        daily_predictions = []
        for _, row in station_info.iterrows():
            lat = row['dmX']
            lon = row['dmY']
            temp, humidity, wind_speed, rain = fetch_weather_data(lat, lon)

            # NaN 값을 기본 값으로 대체
            if np.isnan(temp): temp = 20.0
            if np.isnan(humidity): humidity = 50.0
            if np.isnan(wind_speed): wind_speed = 5.0
            if np.isnan(rain): rain = 0.0

            X_pred = np.array([[future_date.toordinal(), row['dmX'], row['dmY'], future_month, future_hour, temp,
                                humidity, wind_speed, rain]])
            y_pred = model.predict(pd.DataFrame(X_pred,
                                                columns=['DateTime', 'dmX', 'dmY', 'month', 'hour', 'Temperature',
                                                         'Humidity', 'WindSpeed', 'Rain']))[0]

            # 예측 값에 랜덤한 변동 추가
            y_pred += random.uniform(-20, 20)
            y_pred = max(0, y_pred)  # 음수 값을 0으로 제한

            daily_predictions.append({
                'DateTime': future_date.strftime('%Y-%m-%d'),
                'stationName': row['stationName'],
                'dmX': row['dmX'],
                'dmY': row['dmY'],
                'PM10Value': y_pred
            })
        predictions.extend(daily_predictions)
        print(f"Predictions for {future_date.strftime('%Y-%m-%d')} completed.")

    pred_df = pd.DataFrame(predictions)
    print("Predictions generated.")
    return pred_df




def find_top_7_days(pred_df):
    print("Finding top 7 days with the most variation in PM10 values...")
    top_7_days_per_station = []

    # 각 지점별로 변동폭이 큰 7일을 찾기
    for station in station_info['stationName']:
        station_data = pred_df[pred_df['stationName'] == station]
        if not station_data.empty:
            # Calculate day-to-day differences in PM10 values
            station_data['PM10_diff'] = station_data['PM10Value'].diff().abs()
            # Calculate the mean of differences for sorting
            station_data['PM10_diff_mean'] = station_data['PM10_diff'].rolling(window=7, min_periods=1).mean()
            # Sort by mean differences and take the top 7 days
            top_7_days = station_data.nlargest(7, 'PM10_diff_mean')
            top_7_days_per_station.append(top_7_days)

    result_df = pd.concat(top_7_days_per_station)
    print("Top 7 days identified.")
    return result_df


def generate_maps(predictions):
    map_paths = []
    weather_dir = 'D:\\KYB\\Project\\2_WepProject\\3_React\\React_clone_test\\kyb_study\\server\\python\\weather'

    # 디렉토리가 존재하지 않으면 생성
    if not os.path.exists(weather_dir):
        os.makedirs(weather_dir)
        print(f"Directory created: {weather_dir}")  # 로그 추가

    for day in range(1, 8):
        pred_df = pd.DataFrame(predictions)
        pred_df_day = pred_df[pred_df['DateTime'] == pred_df['DateTime'].unique()[day - 1]]
        print(f"Generating map for day {day}, data size: {len(pred_df_day)}")  # 데이터 사이즈 확인

        # 히트맵 데이터 준비
        heatmap_data = pred_df_day[['dmX', 'dmY', 'PM10Value']].values.tolist()

        # Folium 지도 생성
        m = folium.Map(location=[station_info['dmX'].mean(), station_info['dmY'].mean()], zoom_start=7)

        # 히트맵 추가
        heatmap = HeatMap(heatmap_data, radius=20, gradient={0.4: 'green', 0.65: 'yellow', 1: 'red'})
        heatmap.add_to(m)

        # Colormap 추가
        colormap = LinearColormap(['green', 'yellow', 'red'], vmin=0, vmax=100)
        colormap.caption = 'PM10 Concentration Levels'
        colormap.add_to(m)

        # 지도 저장
        map_path = os.path.join(weather_dir, f'predicted_air_quality_map_{day}.html')
        m.save(map_path)
        print(f"Saved map to: {map_path}")  # 로그 추가
        map_paths.append(map_path)

    return map_paths




@mise12random_bp.route('/api/predictions', methods=['GET'])
def predictions():
    print("Fetching air quality data...")
    air_quality_data, weather_data = fetch_air_quality_data()
    air_quality_df = pd.DataFrame(air_quality_data)
    weather_df = pd.DataFrame(weather_data)
    if not air_quality_df.empty:
        model, data = train_model(air_quality_df, weather_df)
        if model and data is not None:
            prediction_data = get_predictions(model, data)
            top_7_days = find_top_7_days(prediction_data)
            print(top_7_days)
            return jsonify(top_7_days.to_dict(orient='records'))
    print("No air quality data fetched or model training failed.")
    return jsonify([])


@mise12random_bp.route('/api/map/<int:day>', methods=['GET'])
def map(day):
    if 1 <= day <= 7:
        map_path = f'D:\\KYB\\Project\\2_WepProject\\3_React\\React_clone_test\\kyb_study\\server\\python\\weather\\predicted_air_quality_map_{day}.html'
        print(f"Checking for map file: {map_path}")  # 로그 추가
        if os.path.exists(map_path):
            print(f"File found: {map_path}")  # 파일 존재 여부 로그
            return send_file(map_path)
        else:
            print(f"File not found: {map_path}")  # 파일 없음 로그
            return jsonify({'error': 'Map file not found.'}), 404
    else:
        print(f"Invalid day requested: {day}")  # 잘못된 day 로그
        return jsonify({'error': 'Invalid day. Please provide a day between 1 and 7.'}), 400


if __name__ == '__main__':
    try:
        print("Starting Flask application...")
        air_quality_data, weather_data = fetch_air_quality_data()
        print(f"Air quality data size: {len(air_quality_data)}")
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
    except Exception as e:
        print("An error occurred:")
        print(str(e))
        print("Traceback:")
        traceback.print_exc()



