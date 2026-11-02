# ruleid: dossier.python.observability.log
log = logging.getLogger(__name__)
# ruleid: dossier.python.observability.log
logging.basicConfig(level=10)
# ruleid: dossier.python.observability.log
slog = structlog.get_logger()
# ruleid: dossier.python.observability.log
logger.info("x")
# ruleid: dossier.python.observability.log
log.exception("x")
# ruleid: dossier.python.observability.log
LOG.debug("x")
# ok: dossier.python.observability.log
cart.info("x")
# ok: dossier.python.observability.log
shop.error("x")

# ruleid: dossier.python.observability.metric
c = prometheus_client.Counter("n", "doc")
# ruleid: dossier.python.observability.metric
statsd.incr("n")
# ok: dossier.python.observability.metric
prometheus_client.start_http_server(8000)

# ruleid: dossier.python.observability.trace
sentry_sdk.init("dsn")
# ruleid: dossier.python.observability.trace
tracer = opentelemetry.trace.get_tracer("x")
# ruleid: dossier.python.observability.trace
tracer2 = trace.get_tracer("y")
# ok: dossier.python.observability.trace
sentry_sdk.capture_message("x")
