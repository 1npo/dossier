import sys

# ruleid: dossier.python.output.stdout
print("hi")
# ruleid: dossier.python.output.stdout
sys.stdout.write("x")
# ruleid: dossier.python.output.stdout
sys.stderr.write("x")
# ok: dossier.python.output.stdout
sys.stdout.flush()

# ruleid: dossier.python.output.file-write
open(path, "w").write(text)
# ruleid: dossier.python.output.file-write
open(path, "ab")
# ruleid: dossier.python.output.file-write
path.write_text("x")
# ruleid: dossier.python.output.file-write
path.write_bytes(b"x")
# ruleid: dossier.python.output.file-write
shutil.copy(a, b)
# ruleid: dossier.python.output.file-write
shutil.move(a, b)
# ok: dossier.python.output.file-write
open(path).read()
# ok: dossier.python.output.file-write
open(path, "rb")

# ruleid: dossier.python.output.outbound-call
requests.get(url)
# ruleid: dossier.python.output.outbound-call
httpx.post(url, json={})
# ruleid: dossier.python.output.outbound-call
client = httpx.Client()
# ruleid: dossier.python.output.outbound-call
urllib.request.urlopen(url)
# ruleid: dossier.python.output.outbound-call
smtplib.SMTP("mail")
# ruleid: dossier.python.output.outbound-call
boto3.client("s3")
# ok: dossier.python.output.outbound-call
cart.get(url)
# ok: dossier.python.output.outbound-call
requests.utils.quote(url)

# ruleid: dossier.python.output.message-produce
channel.basic_publish(exchange="", routing_key="q", body=b"")
# ruleid: dossier.python.output.message-produce
producer.produce("topic", b"x")
# ruleid: dossier.python.output.message-produce
bus.publish("event")
# ok: dossier.python.output.message-produce
bus.subscribe("event")

# ruleid: dossier.python.output.exit-code
sys.exit(1)
# ruleid: dossier.python.output.exit-code
raise SystemExit(2)
# ok: dossier.python.output.exit-code
sys.path.append("x")


def handler(x):
    # ruleid: dossier.python.output.error-response
    abort(404)
    # ruleid: dossier.python.output.error-response
    raise HTTPException(status_code=500)
    # ruleid: dossier.python.output.error-response
    return {"error": "no"}, 404
    # ok: dossier.python.output.error-response
    return {"ok": True}, 200
