FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY apps/api apps/api
COPY apps/__init__.py apps/__init__.py
COPY services services
COPY providers providers
COPY libs libs
COPY data/replay data/replay
RUN useradd --uid 10001 --create-home app
USER 10001
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
