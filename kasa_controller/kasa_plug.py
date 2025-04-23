import os
import sys
import asyncio

from kasa.discover import Discover
from kasa.iot import IotPlug

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from logger import get_logger

class KasaPlug:
    def __init__(self, name : str, ip_address : str):
        self.name = name
        self.ip_address = ip_address
        self.logger = get_logger(self.name)
        
        self.logger.info("Initalizing Kasa plug.")
        self.plug = IotPlug(ip_address)

    async def turn_on(self):
        await self.plug.update()
    
        await self.plug.turn_on()
        self.logger.info(f"Kasa plug at {self.ip_address} is ON.")

    async def turn_off(self):
        await self.plug.update()
        
        await self.plug.turn_off()
        self.logger.info(f"Kasa plug at {self.ip_address} is OFF.")

    async def get_status(self):
        await self.plug.update()
        
        state = "ON" if self.plug.is_on else "OFF"
        self.logger.info(f"Kasa plug at {self.ip_address} is currently {state}.")
        return self.plug.is_on

async def main():
    print("Searching for Kasa devices on the network...")
    devices = await Discover.discover()
    for addr, dev in devices.items():
        await dev.update()
        print(f"{dev.alias} at {addr} ({dev.model})")
        
    ip = input("Enter the IP address of the Kasa plug: ")
    plug = KasaPlug("Plug #1", ip)

    await plug.get_status()
    await plug.turn_off()
    await asyncio.sleep(2)
    await plug.turn_on()

if __name__ == "__main__":
    asyncio.run(main())