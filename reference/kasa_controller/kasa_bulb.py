import os
import sys
import asyncio

from kasa.discover import Discover
from kasa.iot import IotBulb
from typing import Tuple
from dataclasses import dataclass

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from logger import get_logger

@dataclass
class ColorTemp:
    temperature : int
    brightness : int
    
@dataclass
class ColorHSV:
    hue : int
    saturation : int
    brightness : int

class KasaBulb:
    def __init__(self, name :str, ip: str):
        self.name = name
        self.ip = ip
        self.logger = get_logger(self.name)
        
        self.logger.info("Initalizing Kasa bulb.")
        self.bulb = IotBulb(ip)

    async def turn_on(self):
        await self.bulb.turn_on()
        self.logger.info("Turned on.")

    async def turn_off(self):
        await self.bulb.turn_off()
        self.logger.info("Turned off.")

    # Set bulb to a specific HSV color
    async def set_color_hsv(self, color : ColorHSV):
        await self.bulb.set_hsv(color.hue, color.saturation, color.brightness)
        self.logger.info(f"Color set to {color}.")

    async def interpolate_color_hsv(self, target : ColorHSV, duration: float = 1.0, steps: int = 10):
        await self.bulb.update()
        
        self.logger.info(f"Setting color to {target} over the next {duration} seconds...")
        
        start = ColorHSV(
            hue = self.bulb.hue,
            saturation = self.bulb.saturation,
            brightness = self.bulb.brightness
        )
        
        delay = duration / steps
        for i in range(1, steps + 1):
            new_color = ColorHSV(
                hue = int(start.hue + (target.hue - start.hue) * i / steps),
                saturation = int(start.saturation + (target.saturation - start.saturation) * i / steps),
                brightness = int(start.brightness + (target.brightness - start.brightness) * i / steps)
            )
            
            await self.set_color_hsv(new_color)
            await asyncio.sleep(delay)
            
        self.logger.info(f"Interpolation complete color is now at {target}.")

    # Set color temperature in Kelvin: 2500–9000.
    async def set_color_temp(self, color : ColorTemp):
        await self.bulb.set_color_temp(color.temperature)
        await self.bulb.set_brightness(color.brightness)
        
        self.logger.info(f"Color set to {color}.")
        
    async def interpolate_color_temp(self, target: ColorTemp, duration: float = 1.0, steps: int = 10):
        await self.bulb.update()
        
        self.logger.info(f"Setting color to {target} over the next {duration} seconds...")
        
        start = ColorTemp(
            temperature = self.bulb.color_temp,
            brightness = self.bulb.brightness
        )
        
        delay = duration / steps
        for i in range(1, steps + 1):
            new_color = ColorTemp(
                temperature = int(start.temperature + (target.temperature - start.temperature) * i / steps),
                brightness = int(start.brightness + (target.brightness - start.brightness) * i / steps)
            )
            
            await self.set_color_temp(new_color)
            await asyncio.sleep(delay)
            
        self.logger.info(f"Interpolation complete color is now at {target}.")

async def main():
    print("Searching for Kasa devices on the network...")
    devices = await Discover.discover()
    for addr, dev in devices.items():
        await dev.update()
        print(f"{dev.alias} at {addr} ({dev.model})")
        
    ip = input("Enter the IP address of the Kasa plug: ")
    
    bulb = KasaBulb("Buld #1", ip)
    
    await bulb.turn_off()
    await asyncio.sleep(2)
    await bulb.turn_on()

if __name__ == "__main__":
    asyncio.run(main())