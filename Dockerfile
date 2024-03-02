# Start with a Python base image that is compatible with Raspberry Pi's ARM architecture
FROM python:3.12

# Install necessary packages for GPIO access and other dependencies
# RUN apt-get update && apt-get install -y \
#     python3-dev \
#     python3-rpi.gpio \
#     && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the Python script into the container
COPY mqtt-switch2.py .

# Install required Python libraries
RUN pip install --no-cache-dir paho-mqtt gpiozero timeloop Flask

# Environment variables can be defined in the Dockerfile, but it's better to pass them at runtime
# for flexibility and security
# ENV MQTT_HOST=172.16.100.80
# ENV MQTT_PORT=1883
# ...

# Command to run the script
CMD ["python3", "./mqtt-switch2.py"]
