// ruleid: dossier.js.concurrency.thread
const w = new Worker('./job.js');
// ruleid: dossier.js.concurrency.thread
const w2 = new Worker('./job.js', { workerData: 1 });
// ok: dossier.js.concurrency.thread
const q = new Worker('mail', processor);

// ruleid: dossier.js.concurrency.process-pool
child_process.spawn('ls');
// ruleid: dossier.js.concurrency.process-pool
cluster.fork();
// ok: dossier.js.concurrency.process-pool
child.kill();

// ruleid: dossier.js.concurrency.async
await Promise.all([a(), b()]);
// ruleid: dossier.js.concurrency.async
setInterval(tick, 1000);
// ok: dossier.js.concurrency.async
await Promise.resolve(1);

// ruleid: dossier.js.concurrency.lock
const mutex = new Mutex();
// ok: dossier.js.concurrency.lock
const mutexName = 'mutex';

// ruleid: dossier.js.concurrency.queue
const jobs = new Queue('jobs');
// ok: dossier.js.concurrency.queue
const list = new Array();
