import logging

log = logging.getLogger(__name__)  # @io-log-get
CART = {}  # @state-module


def describe():
    from shopcart import cli  # @import-up

    return cli.__name__


def total(items):
    log.info("total")  # @io-log
    try:
        return sum(items)
    except Exception:  # @fail-catchall
        return 0


def unused_helper():  # @dead-func
    return 1
