FROM python:3.11
WORKDIR /bot
COPY requirements.txt /bot/
RUN pip install -r requirements.txt
RUN apt-get update
RUN apt-get install -y ffmpeg
COPY . /bot
CMD python main.py
