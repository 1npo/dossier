# ruleid: dossier.python.resilience.retry
@retry(stop=3)
def a():
    pass


# ruleid: dossier.python.resilience.retry
@tenacity.retry
def b():
    pass


# ruleid: dossier.python.resilience.retry
@backoff.on_exception(backoff.expo, Exception)
def c():
    pass


# ruleid: dossier.python.resilience.retry
adapter = Retry(total=3)

# ok: dossier.python.resilience.retry
@staticmethod
def d():
    pass


# ruleid: dossier.python.resilience.timeout
fetch(url, timeout=5)
# ok: dossier.python.resilience.timeout
fetch(url, retries=5)

# ruleid: dossier.python.resilience.catch-all
try:
    risky()
except:
    pass

# ruleid: dossier.python.resilience.catch-all
try:
    risky()
except Exception:
    pass

# ruleid: dossier.python.resilience.catch-all
try:
    risky()
except Exception as e:
    print(e)

# ruleid: dossier.python.resilience.catch-all
try:
    risky()
except BaseException:
    pass

# ok: dossier.python.resilience.catch-all
try:
    risky()
except ValueError:
    pass

# ruleid: dossier.python.resilience.transaction
with engine.begin():
    pass

# ruleid: dossier.python.resilience.transaction
with transaction.atomic():
    pass

# ruleid: dossier.python.resilience.transaction
conn.rollback()
# ok: dossier.python.resilience.transaction
conn.close()
