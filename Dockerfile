FROM python:3
ENV PYTHONUNBUFFERED 1
WORKDIR /home/django

COPY . .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get update && \
    apt-get install -y iputils-ping openssh-client telnet nano cron&& \
    mkdir /backups /logs

EXPOSE 20-21 8000 65500-65515