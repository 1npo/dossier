// ruleid: dossier.js.resilience.retry
axiosRetry(client, { retries: 3 });
// ruleid: dossier.js.resilience.retry
const options = { retry: 3, other: 1 };
// ok: dossier.js.resilience.retry
const retries = { count: 3 };

// ruleid: dossier.js.resilience.timeout
const config = { timeout: 5000 };
// ruleid: dossier.js.resilience.timeout
const signal = AbortSignal.timeout(100);
// ok: dossier.js.resilience.timeout
const limits = { max: 5 };

// ruleid: dossier.js.resilience.catch-all
try {
  work();
} catch (e) {
  log(e);
}

// ruleid: dossier.js.resilience.catch-all
promise.catch(handle);
// ruleid: dossier.js.resilience.catch-all
process.on('uncaughtException', handle);
// ruleid: dossier.js.resilience.catch-all
app.use((err, req, res, next) => {
  res.end();
});
// ok: dossier.js.resilience.catch-all
app.use((req, res, next) => {
  next();
});

// ruleid: dossier.js.resilience.transaction
await prisma.$transaction([a, b]);
// ruleid: dossier.js.resilience.transaction
await db.transaction(async () => 1);
// ok: dossier.js.resilience.transaction
await db.commit();
