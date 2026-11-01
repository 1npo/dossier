# ruleid: dossier.python.concurrency.thread
t = threading.Thread(target=run)
# ruleid: dossier.python.concurrency.thread
pool = ThreadPoolExecutor(4)
# ok: dossier.python.concurrency.thread
threading.current_thread()

# ruleid: dossier.python.concurrency.process-pool
pp = ProcessPoolExecutor(2)
# ruleid: dossier.python.concurrency.process-pool
p = multiprocessing.Process(target=run)
# ruleid: dossier.python.concurrency.process-pool
mp = multiprocessing.Pool(2)
# ok: dossier.python.concurrency.process-pool
multiprocessing.cpu_count()

# ruleid: dossier.python.concurrency.async
asyncio.run(main())
# ruleid: dossier.python.concurrency.async
asyncio.create_task(job())
# ruleid: dossier.python.concurrency.async
asyncio.gather(a(), b())
# ruleid: dossier.python.concurrency.async
loop.run_until_complete(main())
# ok: dossier.python.concurrency.async
asyncio.sleep(1)

# ruleid: dossier.python.concurrency.lock
a = threading.Lock()
# ruleid: dossier.python.concurrency.lock
b = threading.RLock()
# ruleid: dossier.python.concurrency.lock
c = asyncio.Lock()
# ruleid: dossier.python.concurrency.lock
d = asyncio.Semaphore(3)
# ok: dossier.python.concurrency.lock
threading.Event()

# ruleid: dossier.python.concurrency.queue
q = queue.Queue()
# ruleid: dossier.python.concurrency.queue
aq = asyncio.Queue()
# ruleid: dossier.python.concurrency.queue
mq = multiprocessing.Queue()
# ok: dossier.python.concurrency.queue
collections.deque()
