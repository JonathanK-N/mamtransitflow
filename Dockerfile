# Auteur : Jonathan Kakesa (JonathanK-N).
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
RUN npm install --global pnpm@11.25.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TF_DEBUG=0
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist/
RUN python backend/manage.py collectstatic --noinput && useradd --create-home --uid 10001 transitflow && mkdir -p /data/privatefiles && chown -R transitflow:transitflow /app /data
ENV TF_PRIVATE_STORAGE=/data/privatefiles
USER transitflow
EXPOSE 8000
CMD ["sh", "-c", "python backend/manage.py migrate --noinput && gunicorn --chdir backend transitflow.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 60 --access-logfile - --error-logfile -"]
