FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /app
COPY wakfu_bots ./wakfu_bots
COPY service.py ./service.py
COPY manage.py ./manage.py
RUN mkdir /data && chown 10001:10001 /data
USER 10001:10001
ENV PYTHONUNBUFFERED=1
CMD ["python", "service.py"]
