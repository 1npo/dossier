import os
import sys

# ruleid: dossier.python.input.env-var
home = os.environ["HOME"]
# ruleid: dossier.python.input.env-var
db = os.environ.get("DB", "x.db")
# ruleid: dossier.python.input.env-var
key = os.getenv("KEY")
# ok: dossier.python.input.env-var
cwd = os.getcwd()

# ruleid: dossier.python.input.cli-args
parser.add_argument("--db")
# ruleid: dossier.python.input.cli-args
args = sys.argv
# ruleid: dossier.python.input.cli-args
opt = typer.Option(1)
# ruleid: dossier.python.input.cli-args
arg = typer.Argument(...)
# ok: dossier.python.input.cli-args
parser.parse_args()


# ruleid: dossier.python.input.cli-args
@click.option("--n")
def with_option(n):
    pass


# ruleid: dossier.python.input.cli-args
@click.argument("path")
def with_argument(path):
    pass


# ruleid: dossier.python.input.config-file
data = tomllib.load(f)
# ruleid: dossier.python.input.config-file
cfg = configparser.ConfigParser()
# ruleid: dossier.python.input.config-file
y = yaml.safe_load(text)
# ruleid: dossier.python.input.config-file
load_dotenv()
# ok: dossier.python.input.config-file
tomllib.dumps(data)

# ruleid: dossier.python.input.file-read
text = open(path).read()
# ruleid: dossier.python.input.file-read
raw = open(path, "rb").read()
# ruleid: dossier.python.input.file-read
more = path.read_text()
# ruleid: dossier.python.input.file-read
blob = path.read_bytes()
# ok: dossier.python.input.file-read
open(path, "w")
# ok: dossier.python.input.file-read
open(path, "a+")

# ruleid: dossier.python.input.stdin
line = sys.stdin.readline()
# ruleid: dossier.python.input.stdin
name = input("name: ")
# ok: dossier.python.input.stdin
sys.stdout.flush()

consumer = KafkaConsumer("topic")
# ruleid: dossier.python.input.message-consume
consumer.subscribe(["topic"])
# ruleid: dossier.python.input.message-consume
consumer.poll(1.0)
# ruleid: dossier.python.input.message-consume
channel.basic_consume(queue="q", on_message_callback=cb)

cart = Cart()
# ok: dossier.python.input.message-consume
cart.poll(1.0)
