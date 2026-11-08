const app = express();
const router = Router();
const map = new Map();

// ruleid: dossier.js.entry.http-route
app.get('/', (req, res) => res.send('ok'));

// ruleid: dossier.js.entry.http-route
router.post(
  '/users',
  auth,
  handler,
);

// ruleid: dossier.js.entry.http-route
usersRouter.delete('/users/:id', handler);

// ok: dossier.js.entry.http-route
map.get('users');

// ok: dossier.js.entry.http-route
axios.get('/users');

// ok: dossier.js.entry.http-route
router.get(path, handler);

// ruleid: dossier.js.entry.route-chain
router.route('/cart').get(list).post(add);

// ok: dossier.js.entry.route-chain
axios.route('/cart').get(list);

// ruleid: dossier.js.entry.fastify-route
fastify.route({ method: 'GET', url: '/ping', handler });

// ok: dossier.js.entry.fastify-route
fastify.route({ method: 'GET', handler });

class CatsController {
  // ruleid: dossier.js.entry.nest-route
  @Get(':id')
  find() {
    return 1;
  }

  // ok: dossier.js.entry.nest-route
  @Header('x', 'y')
  other() {
    return 2;
  }
}

// ruleid: dossier.js.entry.server-listen
app.listen(3000);

// ok: dossier.js.entry.server-listen
socket.listen(3000);

// ruleid: dossier.js.entry.cli-command
program.command('sync').action(run);

// ok: dossier.js.entry.cli-command
program.option('-v');

// ruleid: dossier.js.entry.queue-worker
new Worker('mail', async (job) => job.data);

// ok: dossier.js.entry.queue-worker
new Worker('./worker.js', { workerData: 1 });

// ruleid: dossier.js.entry.queue-consume
channel.consume('tasks', handle);

// ok: dossier.js.entry.queue-consume
stream.consume('tasks', handle);

// ruleid: dossier.js.entry.kafka-consumer
consumer.run({ eachMessage: async ({ message }) => message });

// ok: dossier.js.entry.kafka-consumer
consumer.run({ autoCommit: false });

// ruleid: dossier.js.entry.nest-processor
@Processor('video')
class VideoProcessor {}

// ok: dossier.js.entry.nest-processor
@Injectable()
class Plain {}

// ruleid: dossier.js.entry.scheduled-job
cron.schedule('* * * * *', tick);

// ruleid: dossier.js.entry.scheduled-job
new CronJob('0 * * * *', tick);

// ok: dossier.js.entry.scheduled-job
scheduler.schedule('x');

class Jobs {
  // ruleid: dossier.js.entry.nest-cron
  @Cron('0 0 * * *')
  nightly() {
    return 1;
  }

  // ok: dossier.js.entry.nest-cron
  @Interval(1000)
  often() {
    return 2;
  }
}

// ruleid: dossier.js.entry.http-route
router.post( // note
  '/commented',
  handler,
);

const dynamicPath = '/dyn';
// ok: dossier.js.entry.http-route
router.get(dynamicPath, handler);

// ruleid: dossier.js.entry.static-files
app.use(express.static(__dirname + '/assets'));
// ruleid: dossier.js.entry.static-files
server.use('/files', express.static('public'));
// ok: dossier.js.entry.static-files
app.use(express.json());

// ruleid: dossier.js.entry.http-route
api.get('/before-import', handler);

import axios from 'axios';
const client = axios.create();

// ok: dossier.js.entry.http-route
api.post('/comments', body);
// ok: dossier.js.entry.http-route
api.get('/users', { params });
