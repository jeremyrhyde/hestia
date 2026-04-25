from kasa_controller.kasa_bulb import KasaBulb
from kasa_controller.kasa_plug import KasaPlug
from relay_controller.relay import Relay

def load_devices(config):
    devices = config["devices"]
    device_instances = {}

    for name, info in devices.items():
        dtype = info["type"]

        if dtype == "bulb":
            device_instances[name] = [KasaBulb(f"{name.upper()}_{i}", ip) for i, ip in enumerate(info["ips"])]

        elif dtype == "plug":
            device_instances[name] = [KasaPlug(f"{name.upper()}_{i}", ip) for i, ip in enumerate(info["ips"])]

        elif dtype == "relay":
            device_instances[name] = [Relay(f"{name.upper()}_0",info["pin"])]

        else:
            raise ValueError(f"Unknown device type '{dtype}' in {name}")

    return device_instances

    