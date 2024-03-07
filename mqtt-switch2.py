#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import os
import signal
from datetime import datetime, timedelta
import time

from gpiozero import LED
import paho.mqtt.client as mqtt
from threading import Thread, Timer, Event
from flask import Flask, jsonify
from threading import Thread

def gpio_factory(factory):
    if factory == 'rpigpio':
        from gpiozero.pins.rpigpio import RPiGPIOFactory
        return RPiGPIOFactory()
    elif factory == 'pigpio':
        from gpiozero.pins.pigpio import PiGPIOFactory
        return PiGPIOFactory()
    elif factory == 'lgpio':
        from gpiozero.pins.lgpio import LGPIOFactory
        return LGPIOFactory()
    elif factory == 'native':
        from gpiozero.pins.native import NativeFactory
        return NativeFactory()
    else:
        raise ValueError(f"Unknown GPIO factory: {factory}")

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
GPIOZERO_PIN_FACTORY = os.getenv('GPIOZERO_PIN_FACTORY', 'rpigpio') # rpigpio, pigpio, lgpio, native

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# GPIO setup
switch = LED(GPIO_ID, pin_factory=gpio_factory(GPIOZERO_PIN_FACTORY))

last_call = None

class ScheduledTask:
    def __init__(self, interval, function):
        self.interval = interval
        self.function = function
        self.thread = None
        self.stop_event = Event()

    def start(self):
        self.stop_event.clear()
        self.schedule()

    def schedule(self):
        if not self.stop_event.is_set():
            self.thread = Timer(self.interval.total_seconds(), self.run)
            self.thread.start()

    def run(self):
        self.function()
        self.schedule()  # Reschedule the next run

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.cancel()
            self.thread.join()

class MQTTController:
    def __init__(self):
        self.mqttc = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.mqttc.enable_logger(logger)
        self.setup_callbacks()
        self.reconnect_delay = 30

    def setup_callbacks(self):
        self.mqttc.on_message = self.on_message
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_subscribe = self.on_subscribe
        self.mqttc.on_disconnect = self.disconnect_callback

    def connect(self):
        try:
            self.mqttc.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE_INTERVAL)
            self.mqttc.loop_start()
        except Exception as e:
            logger.error(f"Could not connect to MQTT server: {e}. Retrying in {self.reconnect_delay} seconds...")
            self.schedule_reconnect()
    
    def schedule_reconnect(self):
        # Use threading.Timer to schedule a reconnect attempt
        Timer(self.reconnect_delay, self.connect).start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
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
        state = switch.value
        if payload == 'ON' and state != 1:
            switch.on()
            logger.info("Turning on the device.")
        elif payload == 'OFF' and state == 1:
            switch.off()
            logger.info("Turning off the device.")
        self.publish_state()

    def on_subscribe(self, client, userdata, mid, reason_codes, properties):
        logger.info(f"Subscribed to {MQTT_TOPIC_SUB}")

    def disconnect_callback(self, client, userdata, flags, reason_code, properties):
        self.publish_availability('offline')

    def publish_state(self):
        state = 'ON' if switch.is_lit else 'OFF'
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


# Replace the timeloop jobs with instances of ScheduledTask
def scheduled_turn_off_function():
    global last_call
    if last_call and (datetime.now() - last_call).seconds / 60 > AUTOMATIC_SHUTDOWN_DELAY:
        logger.info("No recent activity, turning off the device.")
        switch.off()
        mqtt_controller.publish_state()

def send_availability_and_state_function():
    mqtt_controller.publish_availability('online')
    mqtt_controller.publish_state()
    
@app.route('/health', methods=['GET'])
def health_check():
    if mqtt_controller.mqttc.is_connected():
        return jsonify({'status': 'healthy'}), 200
    else:
        return jsonify({'status': 'unhealthy'}), 503

def run_flask_app():
    app.run(host='0.0.0.0', port=5000)


# Modify the signal_handler function to handle the new ScheduledTask class
def signal_handler(sig, frame):
    logger.info("Gracefully shutting down...")
    scheduled_turn_off.stop()
    send_availability_and_state.stop()
    mqtt_controller.stop()
    
    # Allow time for all threads to finish
    logger.info("Waiting for background processes to terminate...")
    time.sleep(2)
    
    os._exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    flask_thread = Thread(target=run_flask_app)
    flask_thread.start()

    scheduled_turn_off = ScheduledTask(timedelta(seconds=60), scheduled_turn_off_function)
    send_availability_and_state = ScheduledTask(timedelta(seconds=20), send_availability_and_state_function)

    scheduled_turn_off.start()
    send_availability_and_state.start()

    mqtt_controller = MQTTController()
    mqtt_controller.start()
