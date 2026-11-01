from flask import Flask

app = Flask(__name__)


@app.route("/cart")  # @ep-route
def cart():
    return {}


@app.get("/health")  # @ep-route2
def health():
    return "ok"
