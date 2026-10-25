# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Sao_Paulo \
    DJANGO_DEBUG=False \
    DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1] \
    DJANGO_SECRET_KEY_FILE=/data/secret_key \
    SQLITE_PATH=/data/biblioteca.sqlite3 \
    BACKUP_DIR=/data/backups

WORKDIR /app
COPY bibliotecapi/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY bibliotecapi/ ./
COPY docker/ ./docker/
RUN DJANGO_SECRET_KEY=build-only-unused-at-runtime python manage.py collectstatic --noinput \
    && groupadd --gid 10001 biblioteca \
    && useradd --uid 10001 --gid biblioteca --no-create-home biblioteca \
    && mkdir -p /data/backups \
    && chown -R biblioteca:biblioteca /data

USER biblioteca
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "/app/docker/healthcheck.py"]
ENTRYPOINT ["python", "/app/docker/entrypoint.py"]
CMD ["gunicorn", "--config", "/app/docker/gunicorn.conf.py", "bibliotecapi.wsgi:application"]
