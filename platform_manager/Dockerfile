FROM python:3.8-slim
COPY requirements.txt .
COPY wait-for-it.sh .
COPY wait-for-kafka.sh .

RUN apt-get update && apt-get install -y curl jq sshpass && curl -sL https://aka.ms/InstallAzureCLIDeb | bash

RUN pip install -r requirements.txt
RUN cp /usr/share/zoneinfo/Asia/Kolkata /etc/localtime && \
echo "Asia/Kolkata" >  /etc/timezone
ADD platform_manager platform_manager
ENTRYPOINT ["/wait-for-kafka.sh", "platform_manager"]