import os
import sqlite3

DB = os.environ.get("SHOP_DB", "shop.db")  # @io-env


def connect():
    return sqlite3.connect(DB)  # @io-db-connect


def save(path, text):
    open(path, "w").write(text)  # @io-file-write


def load(path):
    return open(path).read()  # @io-file-read


def fetch(url):
    import requests

    return requests.get(url, timeout=5)  # @io-outbound
