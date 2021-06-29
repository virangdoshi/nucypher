FROM python:3.10.0b2-slim

# Update
RUN apt update -y && apt upgrade -y
RUN apt install patch gcc libffi-dev wget -y

WORKDIR /code
COPY . /code

RUN pip3 install .[ursula]

CMD ["/bin/bash"]
