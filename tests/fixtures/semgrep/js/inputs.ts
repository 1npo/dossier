// ruleid: dossier.js.inputs.env-var
const port = process.env.PORT;
// ruleid: dossier.js.inputs.env-var
const key = process.env['API_KEY'];
// ruleid: dossier.js.inputs.env-var
const mode = import.meta.env.VITE_MODE;
// ok: dossier.js.inputs.env-var
const env = { PORT: 1 };

// ruleid: dossier.js.inputs.cli-args
const args = process.argv.slice(2);
// ruleid: dossier.js.inputs.cli-args
program.option('-v, --verbose');
// ruleid: dossier.js.inputs.cli-args
const parsed = minimist(args);
// ok: dossier.js.inputs.cli-args
const argv = getArgv();

// ruleid: dossier.js.inputs.config-file
dotenv.config();
// ok: dossier.js.inputs.config-file
settings.config();

// ruleid: dossier.js.inputs.file-read
const text = fs.readFileSync('a.txt', 'utf8');
// ruleid: dossier.js.inputs.file-read
const more = await fsp.readFile('b.txt');
// ok: dossier.js.inputs.file-read
fs.writeFile('a.txt', 'x', done);

// ruleid: dossier.js.inputs.stdin
process.stdin.on('data', handle);
// ok: dossier.js.inputs.stdin
process.stdout.write('x');

// ruleid: dossier.js.inputs.message-consume
bus.subscribe('orders', handle);
// ruleid: dossier.js.inputs.message-consume
socket.on('message', handle);
// ok: dossier.js.inputs.message-consume
socket.on('open', handle);

// ruleid: dossier.js.inputs.file-read
app.use(express.static(__dirname + '/assets'));
// ruleid: dossier.js.inputs.request-header
const token = req.headers.authorization;
// ruleid: dossier.js.inputs.request-header
const agent = request.header('user-agent');
// ruleid: dossier.js.inputs.request-header
const host = req.get('host');
// ruleid: dossier.js.inputs.request-header-destructured
const { authorization } = req.headers;
// ok: dossier.js.inputs.request-header-destructured
const { name } = req.body;
// ok: dossier.js.inputs.request-header
const body = req.body;
// ok: dossier.js.inputs.request-header
const other = new Map().get('host');
