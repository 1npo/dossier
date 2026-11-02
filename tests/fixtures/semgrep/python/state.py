# ruleid: dossier.python.state.db-connect
conn = sqlite3.connect("x.db")
# ruleid: dossier.python.state.db-connect
engine = create_engine("sqlite://")
# ruleid: dossier.python.state.db-connect
pg = psycopg2.connect("dsn")
# ruleid: dossier.python.state.db-connect
r = redis.Redis()
# ruleid: dossier.python.state.db-connect
m = pymongo.MongoClient()
# ok: dossier.python.state.db-connect
sqlite3.version

# ruleid: dossier.python.state.db-access
cur.execute("select 1")
# ruleid: dossier.python.state.db-access
cur.executemany("insert", rows)
# ruleid: dossier.python.state.db-access
rows = session.query(Order)
# ruleid: dossier.python.state.db-access
session.add(order)
# ruleid: dossier.python.state.db-access
session.commit()
# ok: dossier.python.state.db-access
cart.remove(item)


def bump():
    # ruleid: dossier.python.state.global-state
    global COUNTER
    COUNTER += 1


def local_only():
    # ok: dossier.python.state.global-state
    counter = 1
    return counter


# ruleid: dossier.python.state.cache
@functools.lru_cache
def a():
    pass


# ruleid: dossier.python.state.cache
@lru_cache(maxsize=10)
def b():
    pass


# ruleid: dossier.python.state.cache
@functools.cache
def c():
    pass


# ruleid: dossier.python.state.cache
@cached_property
def d(self):
    pass


# ok: dossier.python.state.cache
@property
def e(self):
    pass
