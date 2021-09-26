FROM python:3
ENV PYTHONUNBUFFERED 1
WORKDIR /home/django

COPY . .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get update && \
    apt-get install -y iputils-ping openssh-client nano cron vsftpd && \
    mkdir /backups /logs /diffs && \
    useradd -g root -d /home/ftp -ms /bin/bash -p '$y$j9T$JLWYUcbrlah2TxEKzjiNS/$45EZ6hF1evpn5bCtlXbOkyvagZTVmKLC19Kq8U4cen9' ftpuser && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /var/run/vsftpd/empty

EXPOSE 20-21
EXPOSE 8000
EXPOSE 65500-65515