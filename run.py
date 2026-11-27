"""Start the paper-trading bot:  python run.py"""
import logging

from bot.live import Trader

logging.basicConfig(filename="bot.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger().addHandler(logging.StreamHandler())
Trader().run_forever()
