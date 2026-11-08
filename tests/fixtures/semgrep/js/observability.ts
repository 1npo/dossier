// ruleid: dossier.js.observability.log
console.info('started');
// ruleid: dossier.js.observability.log
logger.warn('slow');
// ruleid: dossier.js.observability.log
const l = pino({ level: 'info' });
// ok: dossier.js.observability.log
cart.log('x');
// ok: dossier.js.observability.log
console.table(rows);

// ruleid: dossier.js.observability.metric
const hits = new Counter({ name: 'hits' });
// ruleid: dossier.js.observability.metric
statsd.increment('requests');
// ok: dossier.js.observability.metric
statsd.close();

// ruleid: dossier.js.observability.trace
Sentry.init({ dsn });
// ruleid: dossier.js.observability.trace
const tracer = trace.getTracer('app');
// ok: dossier.js.observability.trace
Sentry.captureMessage('x');
