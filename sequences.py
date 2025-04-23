import time

from typing import List

from kasa_controller.kasa_bulb import KasaBulb, ColorTemp, ColorHSV
from kasa_controller.kasa_plug import KasaPlug
from relay_controller.relay import Relay
from logger.logger import get_logger

class LightSequence:
    
    def __init__(self, name : str, devices):
        self.name = name
        self.actions = []
        self.logger = get_logger(self.name)
        self.logger.info("Initializing lighting sequence...")
        self.lights = devices
        
    async def turn_on(self):
        self.logger.info("Turning lights on.")
        for light in self.lights:
            await light.turn_on()
        
    async def turn_off(self):
        self.logger.info("Turning lights off.")
        for light in self.lights:
            await light.turn_off()
        
    async def set_color(self, color):
        self.logger.info("Setting lights to {color}.")
        for light in self.lights:
            if type(light) == KasaPlug:
                self.logger.error("Invalid call to set_color when using device type 'plug'")
                continue
                
            if type(color) == ColorHSV:
                await light.set_color_hsv(color)
            elif type(color_ == ColorTemp):
                await light.set_color_temp(color)
            else:
                self.logger.error(f"Invalid color type: {type(color)}")
                
       
    async def dim(self, color, dim_timer = 0):

        self.logger.info("Setting lights to {color} (Dim Timer = {dim}s).")
        for light in self.lights:
            if type(light) == KasaPlug:
                self.logger.error("Invalid call to set_color when using device type 'plug'")
                continue
            
            if type(color) == ColorHSV:
                if dim_timer:
                    await light.interpolate_color_hsv(color, dim_timer)
                else:
                    await light.set_color_hsv(color)
            elif type(color == ColorTemp):
                if dim_timer:
                    await light.interpolate_color_temp(color, dim_timer)
                else:
                    await light.set_color_temp(color)
            else:
                self.logger.error(f"Invalid color type: {type(color)}")
                raise "Invalid color type"
            
    def add_action(self, function: str, time: int):
        self.logger.info(f"Adding function: {function} at time: {time}")
        self.actions.append({
            "function": function,
            "time": time
        })
        
    async def run_action(self, function):
        if function == "TURN_ON":
            await self.turn_on()
        elif function == "TURN_OFF":
            await self.turn_off()
        elif function == "DIM":
            await self.dim(ColorTemp(4000, 30), 300)
        else:
            self.logger.info(f"Invalid light function {function}")
            
    def shutdown(self):
        self.logger.info("Shutting down light sequence.")
            
     
class CoffeeSequence:
    
    def __init__(self, name : str, device):
        self.name = name
        self.actions = []
        self.logger = get_logger(self.name)
        self.logger.info("Initializing coffee sqeuence...")
        
        self.relay = device
        
    def press(self, delay = 5):
        self.logger.info("Pressing button for 5 secs...")
        
        self.relay.on()
        time.sleep(delay)
        self.relay.off()
        
    def activate(self):
        self.logger.info("Activating coffee machine...")
        
        self.press()
        time.sleep(60)
        self.press()    
        
    def add_action(self, function: str, time: int):
        self.logger.info(f"Adding function: {function} at time: {time}")
        self.actions.append({
            "function": function,
            "time": time
        })
        
    def run_action(self, function):
        if function == "RUN":
            self.activate()
        else:
            self.logger.info(f"Invalid coffee function {function}")
             
    def shutdown(self):
        self.logger.info("Shutting down coffee machine.")
        self.relay.cleanup()

def load_sequences(config, device_instances):
    sequence_definitions = config["sequences"]
    sequences = []

    for sequence_name, events in sequence_definitions.items():

        for event in events:
            sequence_type = event["sequence_type"]
            function = event["function"]
            time = float(event["time"])  # handle float hour
            event_devices = event["devices"]
            
            # List devices for sequence
            devices = []
            for event_device in event_devices:
                devices = devices + device_instances[event_device]
                
            # Create sequence
            if sequence_type == "lighting":
                sequence = LightSequence(sequence_name.upper(), devices)
            elif sequence_type == "coffee":
                sequence = CoffeeSequence(sequence_name.upper(), devices[0])
            else:
                raise ValueError(f"Unknown sequence type: {sequence_type}")

            sequence.add_action(function, time)
            sequences.append(sequence)

    return sequences
