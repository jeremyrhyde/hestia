import os
import sys
import time

import RPi.GPIO as GPIO

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from logger import get_logger

class Relay:
    def __init__(self, name, signal_pin):
        self.name = name
        self.signal_pin = signal_pin
        self.logger = get_logger(self.name)
        
        self.logger.info("Initalizing relay.")
        self.setup()
        
        self.off()  # Ensure it's off by default

    def setup(self):
        self.logger.info("Setting up GPIO, mode BCM")
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.signal_pin, GPIO.OUT)
        
    def on(self):
        self.logger.info(f"Turning on.")
    
        GPIO.output(self.signal_pin, GPIO.HIGH)

    def off(self):
        self.logger.info(f"Turning off.")
        
        GPIO.output(self.signal_pin, GPIO.LOW)

    def cleanup(self):
        self.logger.info("Cleaning up GPIO.")
        GPIO.cleanup()

# Example usage:
if __name__ == "__main__":
    
    while True:
        pin_input = input("Enter the GPIO pin number to control the relay: ")
        signal_pin = int(pin_input)
        
        relay = Relay("test", signal_pin=signal_pin)  # Replace with your actual GPIO pin

        try:
            relay.on()
            time.sleep(2)
            relay.off()
        finally:
            relay.cleanup()
