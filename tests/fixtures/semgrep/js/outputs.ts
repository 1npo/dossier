// ruleid: dossier.js.outputs.stdout
console.log('hello');
// ruleid: dossier.js.outputs.stdout
process.stderr.write('bad');
// ok: dossier.js.outputs.stdout
logger.write('x');

// ruleid: dossier.js.outputs.file-write
fs.writeFileSync('out.txt', 'x');
// ruleid: dossier.js.outputs.file-write
const out = fs.createWriteStream('o.log');
// ok: dossier.js.outputs.file-write
fs.readFile('in.txt', done);

// ruleid: dossier.js.outputs.outbound-call
const res = await fetch('https://example.com/a');
// ruleid: dossier.js.outputs.outbound-call
axios.get('https://example.com/b');
// ruleid: dossier.js.outputs.outbound-call
apiClient.post('/orders', body);
// ok: dossier.js.outputs.outbound-call
cache.get('key');
// ok: dossier.js.outputs.outbound-call
const f = fetchLocal('x');

// ruleid: dossier.js.outputs.message-produce
mailQueue.add('send', data);
// ruleid: dossier.js.outputs.message-produce
producer.send({ topic: 'orders', messages: [] });
// ruleid: dossier.js.outputs.message-produce
channel.sendToQueue('tasks', buf);
// ok: dossier.js.outputs.message-produce
set.add(1);

// ruleid: dossier.js.outputs.exit-code
process.exit(1);
// ruleid: dossier.js.outputs.exit-code
process.exitCode = 2;
// ok: dossier.js.outputs.exit-code
process.on('exit', done);

// ruleid: dossier.js.outputs.error-response
res.status(404).send('no');
// ruleid: dossier.js.outputs.error-response
throw new BadRequestException('bad');
// ruleid: dossier.js.outputs.error-response
notFound();
// ok: dossier.js.outputs.error-response
res.status(200).send('ok');
// ok: dossier.js.outputs.error-response
throw new Error('plain');
