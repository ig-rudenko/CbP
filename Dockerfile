FROM python:3
ENV PYTHONUNBUFFERED 1
WORKDIR /home/django

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y iputils-ping openssh-client nano
RUN mkdir /backups /logs /diffs


COPY ./cbp ./cbp
COPY ./CbP_web ./CbP_web
COPY ./static ./static
COPY ./templates ./templates
COPY ./backup.py .
COPY ./cbp.conf .
COPY ./manage.py .
COPY ./requirements.txt .
COPY ./run.sh .