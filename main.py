import os
import yaml
import time
import asyncio

from datetime import datetime

from devices import load_devices
from sequences import load_sequences
from logger.logger import get_logger, reset_logging

config_path = "config.yaml"       

async def run_scheduler_loop(logger, sequences: list, check_interval_seconds: int = 30):
    triggered = set()

    try:
        while True:
            print("hi")
            now = datetime.now()
            current_time_float = now.hour + now.minute / 60.0
            current_day = now.date()
            
            logger.info(f"Checking for actions at: {current_time_float:.2f}")

            for sequence in sequences:
                for action in sequence.actions:
                    action_time = float(action["time"])
                    action_key = (sequence.name, action_time, action["function"], current_day)

                    # Trigger if within +/- 0.5 minute (~0.0083 hour) of target time
                    if abs(current_time_float - action_time) < 0.01 and action_key not in triggered:
                        logger.info(f"[{now.strftime('%H:%M')}] Running '{action['function']}' for '{sequence.name}' (scheduled: {action_time:.2f})")
                        await sequence.run_action(action["function"])
                        triggered.add(action_key)

            # Wait before checking again
            time.sleep(check_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Cleaning up and exiting...")
    
    
async def main():
    reset_logging()
    
    logger = get_logger("MAIN")
    logger.info("Starting main down program...")
    
    
    logger.info(f"Loading config from {config_path}...")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    logger.info(f"Initializing devices...")
    devices = load_devices(config)  

    logger.info(f"Loading sequences...")
    sequences = load_sequences(config, devices)  

    
    logger.info(f"Running sequences...")
    await run_scheduler_loop(logger, sequences)
    
    
    logger.info("Shutting down main program.")
    for sequence in sequences:
        print(sequence.actions)
        sequence.shutdown()
    logger.info("Shutting down complete.")

# Example usage:
if __name__ == "__main__":
    asyncio.run(main())
