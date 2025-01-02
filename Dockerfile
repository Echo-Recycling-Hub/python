# Python 3.12.3 을 기반
FROM python:3.12.3-alpine3.20

# 필수 시스템 패키지들을 설치
RUN apk add --no-cache  \
# C 컴파일러 (일부 python 패키지 빌드에 필요)
    gcc  \
    # C 라이브러리 개발 파일
    musl-dev  \
    # 리눅스 커널 헤더파일
    linux-headers  \
    #  Python 개발 파일 (일부 패키지 설치시 필요)
    python3-dev  \
    # Foreign Funtion interface 개발라이브러리 
    libffi-dev  \
    # SSL 지원을 위한 OpenSSl 개발 파일
    openssl-dev  \
    # Rust 패키지 매니저 (일부 Python 패키지에서 필요)
    cargo


#  애플리케이션 코드가 위치할 디렉토리 설정
WORKDIR /code

#  requirments.txt 파일만 먼저 복사
#  이렇게 해두면 requierments 만 변경되었을때만 pip install 을 실행
COPY ./reuierments.txt /code/reuierments.txt

# Python 패키지 설치
#  --no-cache-dir: pip 캐시를 사용하지 않아 이미지 크기 감소
#  --upgrade : 최신버전으로 설치
RUN pip install --no-cache-dir --upgrade -r /code/requirments.txt

# 애플리케이션 시작 스크립트를 복사하고 실행 권한을 부여
COPY ./entry_point.sh /code/entry_point.sh
RUN chmod +x /code/entry_point.sh

# 현재 디렉토리의 모든 파일을 컨테이너의 /code 디렉토리로 복사
COPY ./ ./

# 컨테이너가 80번 포트를 사용함을 명시
# flask 앱이 80번 포트에서 실행되도록 설정해야 함.
EXPOSE 80

# 컨테이너 시작 시 entry_point.sh 스크립트를 실행
CMD ["sh", "/code/entry_point.sh"]