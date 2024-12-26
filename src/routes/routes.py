# routes.py
import pandas as pd
from flask import Blueprint, jsonify, request
from sqlalchemy import create_engine
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from konlpy.tag import Okt

recommend_bp = Blueprint('recommend_bp', __name__)

# SQLAlchemy 엔진 생성
engine = create_engine('oracle+cx_oracle://kyb:1111@localhost:1521/xe')

# 데이터 가져오기
query_zero = "SELECT id, info, hash_tags, name FROM zero"
query_zero_re = "SELECT id, review, review2, review3, review4, review5, review6 FROM zero_re"

df_zero = pd.read_sql(query_zero, con=engine)
df_zero_re = pd.read_sql(query_zero_re, con=engine)

# 리뷰 데이터 병합
df_zero_re['combined_reviews'] = df_zero_re.apply(lambda row: ' '.join(row[['review', 'review2', 'review3', 'review4', 'review5', 'review6']].values.astype(str)), axis=1)

# zero 테이블과 zero_re 테이블 병합
df_merged = pd.merge(df_zero, df_zero_re, on='id')

# 형태소 분석기 초기화
okt = Okt()

# 한국어 텍스트 전처리 함수
def preprocess_korean_text(text):
    tokens = okt.morphs(text)
    return ' '.join(tokens)

# 정보, 해시태그, 리뷰 데이터 병합 (None 값을 빈 문자열로 처리)
df_merged['combined_text'] = df_merged.apply(lambda row: ' '.join([str(row['info']) if row['info'] else '',
                                                                   str(row['hash_tags']) if row['hash_tags'] else '',
                                                                   str(row['combined_reviews']) if row['combined_reviews'] else '']), axis=1)

# 병합된 텍스트 데이터 전처리
df_merged['processed_text'] = df_merged['combined_text'].apply(preprocess_korean_text)

# TF-IDF 벡터화
tfidf_vectorizer = TfidfVectorizer()
tfidf_matrix = tfidf_vectorizer.fit_transform(df_merged['processed_text'])

# 코사인 유사도 계산
cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

# 추천 함수 정의
def get_recommendations(index, cosine_sim=cosine_sim):
    sim_scores = list(enumerate(cosine_sim[index]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    sim_scores = sim_scores[1:6]  # 상위 5개의 유사한 리뷰 선택
    review_indices = [i[0] for i in sim_scores]
    return df_merged.iloc[review_indices]

@recommend_bp.route('/recommend/<int:index>', methods=['GET'])
def recommend(index):
    recommendations = get_recommendations(index)
    return jsonify(recommendations[['id', 'name', 'info', 'hash_tags', 'review', 'review2', 'review3', 'review4', 'review5', 'review6']].to_dict(orient='records'))
