import click


# ruleid: dossier.python.entry.main-guard
if __name__ == "__main__":
    pass

# ok: dossier.python.entry.main-guard
if __name__ == "other":
    pass


# ruleid: dossier.python.entry.click-command
@click.command()
def run():
    pass


# ruleid: dossier.python.entry.click-command
@click.group
def tools():
    pass


# ruleid: dossier.python.entry.click-command
@tools.command("sub")
def sub():
    pass


# ok: dossier.python.entry.click-command
@staticmethod
def plain():
    pass


# ruleid: dossier.python.entry.http-route
@app.route("/cart")
def cart():
    return {}


# ruleid: dossier.python.entry.http-route
@app.get("/health")
def health():
    return "ok"


# ok: dossier.python.entry.http-route
@app.before_request("x")
def hook():
    return None


urlpatterns = [
    # ruleid: dossier.python.entry.django-url
    path("cart/", views.cart),
    # ruleid: dossier.python.entry.django-url
    re_path(r"^old/$", views.old),
]

# ok: dossier.python.entry.django-url
other = path("x", views.x)


# ruleid: dossier.python.entry.celery-task
@app.task
def send():
    pass


# ruleid: dossier.python.entry.celery-task
@shared_task(bind=True)
def build(self):
    pass


# ok: dossier.python.entry.celery-task
@app.errorhandler(404)
def missing(e):
    pass


# ruleid: dossier.python.entry.scheduled-job
sched.add_job(run, "interval", minutes=5)

# ruleid: dossier.python.entry.scheduled-job
schedule.every(10).minutes.do(run)

# ok: dossier.python.entry.scheduled-job
sched.remove_job("x")


# ruleid: dossier.python.entry.argparse-subcommand
commands.add_parser("serve", help="run the server")

# ruleid: dossier.python.entry.argparse-subcommand
watch_add = watch_commands.add_parser(
    "add",
    help="add a watch",
)

# ok: dossier.python.entry.argparse-subcommand
commands.add_parser(name, help=help)

# ok: dossier.python.entry.argparse-subcommand
parser.add_argument("serve")

# ruleid: dossier.python.entry.cli-helper-command
init = add('init', cmd_init, 'write an example config file')

# ruleid: dossier.python.entry.cli-helper-command
add("sites", cmd_sites, "list the sites")

# ok: dossier.python.entry.cli-helper-command
add(name, handler, help)

# ok: dossier.python.entry.cli-helper-command
add("total", compute_total, "not a command handler")
