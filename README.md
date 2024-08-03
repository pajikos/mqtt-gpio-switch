Here's a README.md file for your GitHub project:

```markdown
# Raspberry Pi MQTT Relay Control

This project implements a remote control system for a relay switch on a Raspberry Pi using MQTT protocol. It provides both MQTT-based control and a web interface for managing the relay switch.

## Features

- Control a relay switch connected to a Raspberry Pi GPIO pin
- MQTT integration for remote control
- Automatic shutdown after a period of inactivity
- Web interface for manual control and status monitoring
- Configurable via environment variables
- Docker support for easy deployment

## Requirements

- Raspberry Pi (any model with GPIO pins)
- Python 3.6+
- MQTT Broker (e.g., Mosquitto)
- Docker (optional)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/rpi-mqtt-relay-control.git
   cd rpi-mqtt-relay-control
   ```

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

## Configuration

The application can be configured using environment variables. Here are the available options:

- `MQTT_HOST`: MQTT broker address (default: "172.16.100.80")
- `MQTT_PORT`: MQTT broker port (default: 1883)
- `MQTT_KEEPALIVE_INTERVAL`: MQTT keepalive interval in seconds (default: 45)
- `MQTT_TOPIC`: MQTT topic for publishing switch state (default: "home/kotel")
- `MQTT_TOPIC_SUB`: MQTT topic for subscribing to switch commands (default: "home/kotel/set")
- `MQTT_TOPIC_AVAILABILITY`: MQTT topic for availability status (default: "home/kotel/availability")
- `AUTOMATIC_SHUTDOWN_DELAY`: Delay in minutes before automatic shutdown (default: 15)
- `GPIO_ID`: GPIO pin number for the relay switch (default: 21)
- `GPIOZERO_PIN_FACTORY`: GPIO pin factory to use (default: 'rpigpio')

## Usage

1. Start the application:
   ```
   python3 main.py
   ```

2. The application will start and connect to the MQTT broker.

3. Control the relay switch by publishing "ON" or "OFF" to the `MQTT_TOPIC_SUB`.

4. Access the web interface at `http://<raspberry_pi_ip>:5000/control`.

## Docker Deployment

1. Build the Docker image:
   ```
   docker build -t rpi-mqtt-relay-control .
   ```

2. Run the Docker container:
   ```
   docker run -d --privileged --name rpi-mqtt-relay \
     -e MQTT_HOST=your_mqtt_broker_ip \
     -p 5000:5000 \
     rpi-mqtt-relay-control
   ```

   Note: The `--privileged` flag is required to access GPIO pins from within the container.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).
```

This README provides an overview of your project, its features, installation instructions, configuration options, usage guide, and information on Docker deployment. You may want to customize it further based on your specific project details or add any additional sections you find relevant.