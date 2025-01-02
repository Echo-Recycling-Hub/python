#!/bin/sh

# 환경 변수 기본값 설정 (필요한 경우)
: ${PORT:=8000}
: ${HOST:=0.0.0.0}
: ${WORKERS:=4}

# 애플리케이션 시작 전 초기화 작업
echo "Starting application on $HOST:$PORT with $WORKERS workers"

# 데이터베이스 마이그레이션 등 초기화 작업이 필요한 경우
# python manage.py db upgrade

# Gunicorn으로 애플리케이션 실행
# Gunicorn은 프로덕션 환경에서 권장되는 WSGI 서버입니다
exec gunicorn main:app \
    --bind $HOST:$PORT \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile - \
    --error-logfile - \
    --log-level info

# 만약 Gunicorn을 사용하지 않는다면:
# exec python main.py