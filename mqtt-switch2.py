#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import os
import signal
from datetime import datetime, timedelta

import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt
from timeloop import Timeloop
from flask import Flask, jsonify
from threading import Thread

app = Flask(__name__)


# Configuration constants updated to load from environment variables
MQTT_HOST = os.getenv('MQTT_HOST', "172.16.100.80")
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_KEEPALIVE_INTERVAL = int(os.getenv('MQTT_KEEPALIVE_INTERVAL', 45))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', "home/kotel")
MQTT_TOPIC_SUB = os.getenv('MQTT_TOPIC_SUB', "home/kotel/set")
MQTT_TOPIC_AVAILABILITY = os.getenv('MQTT_TOPIC_AVAILABILITY', "home/kotel/availability")
AUTOMATIC_SHUTDOWN_DELAY = int(os.getenv('AUTOMATIC_SHUTDOWN_DELAY', 15))
GPIO_ID = int(os.getenv('GPIO_ID', 21))

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_ID, GPIO.OUT)

# Timeloop for scheduled tasks
tl = Timeloop()
last_call = None

class MQTTController:
    def __init__(self):
        self.mqttc = mqtt.Client(callback_api_version=5.0)
        self.mqttc.enable_logger(logger)
        self.setup_callbacks()

    def setup_callbacks(self):
        self.mqttc.on_message = self.on_message
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_subscribe = self.on_subscribe
        self.mqttc.on_disconnect = self.disconnect_callback

    def connect(self):
        try:
            self.mqttc.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE_INTERVAL)
        except Exception as e:
            logger.error("Could not connect to MQTT server: %s. Retrying in 60 seconds...", e)
            tl.job(interval=timedelta(seconds=30))(self.connect)

    def on_connect(self, client, userdata, flags, rc):
        self.publish_availability('online')
        self.mqttc.subscribe(MQTT_TOPIC_SUB, 0)
        logger.info(f"Connected to MQTT broker at {MQTT_HOST}")

    def on_message(self, client, userdata, msg):
        global last_call
        payload = msg.payload.decode("utf-8")
        logger.info(f"Received message on topic {msg.topic}: {payload}")
        last_call = datetime.now()
        self.handle_message(payload)

    def handle_message(self, payload):
        state = GPIO.input(GPIO_ID)
        if payload == 'ON' and state != 1:
            GPIO.output(GPIO_ID, True)
            logger.info("Turning on the device.")
        elif payload == 'OFF' and state == 1:
            GPIO.output(GPIO_ID, False)
            logger.info("Turning off the device.")
        self.publish_state()

    def on_subscribe(self, client, userdata, mid, granted_qos):
        logger.info(f"Subscribed to {MQTT_TOPIC_SUB} with QoS {granted_qos}")

    def disconnect_callback(self, client, userdata, rc):
        self.publish_availability('offline')

    def publish_state(self):
        state = 'ON' if GPIO.input(GPIO_ID) == 1 else 'OFF'
        logger.info(f"Publishing state {state} to {MQTT_TOPIC}")
        self.mqttc.publish(MQTT_TOPIC, state, qos=0, retain=True)

    def publish_availability(self, availability):
        logger.info(f"Publishing availability {availability} to {MQTT_TOPIC_AVAILABILITY}")
        self.mqttc.publish(MQTT_TOPIC_AVAILABILITY, availability, qos=0, retain=False)

    def start(self):
        self.connect()
        self.mqttc.loop_start()

    def stop(self):
        self.mqttc.loop_stop()
        self.publish_availability('offline')
        self.mqttc.disconnect()

# Scheduled job to turn off GPIO after delay
@tl.job(interval=timedelta(seconds=60))
def scheduled_turn_off():
    global last_call
    if last_call and (datetime.now() - last_call).seconds / 60 > AUTOMATIC_SHUTDOWN_DELAY:
        logger.info("No recent activity, turning off the device.")
        GPIO.output(GPIO_ID, False)
        mqtt_controller.publish_state()

@tl.job(interval=timedelta(seconds=20))
def send_availability_and_state():
    mqtt_controller.publish_availability('online')
    mqtt_controller.publish_state()
    
@app.route('/health', methods=['GET'])
def health_check():
    if mqtt_controller.mqttc.is_connected() and tl.is_running():
        return jsonify({'status': 'healthy'}), 200
    else:
        return jsonify({'status': 'unhealthy'}), 503

def run_flask_app():
    app.run(host='0.0.0.0', port=5000)

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    logger.info("Gracefully shutting down...")
    tl.stop()
    mqtt_controller.stop()
    GPIO.cleanup()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    flask_thread = Thread(target=run_flask_app)
    flask_thread.start()

    mqtt_controller = MQTTController()
    mqtt_controller.start()
    tl.start(block=True)
