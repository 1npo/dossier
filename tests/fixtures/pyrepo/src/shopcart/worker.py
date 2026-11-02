import asyncio
import threading

lock = threading.Lock()  # @cc-lock


def start():
    threading.Thread(target=run).start()  # @cc-thread


async def run_async():
    await asyncio.sleep(0)


def run():
    asyncio.run(run_async())  # @cc-async
