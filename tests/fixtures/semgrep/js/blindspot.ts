const name = pick();

// ruleid: dossier.js.blindspot.dynamic-import
const mod = await import(`./${name}`);
// ok: dossier.js.blindspot.dynamic-import
const lazy = await import('./lazy');

// ruleid: dossier.js.blindspot.dynamic-require
const plugin = require(name);
// ok: dossier.js.blindspot.dynamic-require
const fixed = require('./fixed');

// ruleid: dossier.js.blindspot.barrel-reexport
export * from './a';
// ruleid: dossier.js.blindspot.barrel-reexport
export { b } from './b';
// ok: dossier.js.blindspot.barrel-reexport
export const own = 1;

// ruleid: dossier.js.blindspot.react-context
const Ctx = createContext(null);
// ruleid: dossier.js.blindspot.react-context
const value = useContext(Ctx);
// ok: dossier.js.blindspot.react-context
const plain = useState(0);

// ruleid: dossier.js.blindspot.hook-wiring
export function useCart() {
  return 1;
}
// ok: dossier.js.blindspot.hook-wiring
export function cartTotal() {
  return 2;
}

// ruleid: dossier.js.blindspot.string-route
router.get(path, handler);
// ok: dossier.js.blindspot.string-route
router.get('/fixed', handler);
// ok: dossier.js.blindspot.string-route
cache.get(key, handler);

// ruleid: dossier.js.blindspot.route-mount
app.use('/api', api);
// ruleid: dossier.js.blindspot.route-mount
express.Router().use('/api', api);
// ruleid: dossier.js.blindspot.route-mount
Router().use('/v1', v1);
// ok: dossier.js.blindspot.route-mount
app.use(cors());

// ruleid: dossier.js.blindspot.module-federation
new ModuleFederationPlugin({ name: 'shell' });
// ruleid: dossier.js.blindspot.module-federation
const remotes = { remotes: { cart: 'cart@http://x/entry.js' } };
// ok: dossier.js.blindspot.module-federation
const federate = 1;

// ruleid: dossier.js.blindspot.di-registration
@Injectable()
class Service {}
// ruleid: dossier.js.blindspot.di-registration
container.bind(Service);
// ok: dossier.js.blindspot.di-registration
@Entity()
class Row {}

// ruleid: dossier.js.blindspot.computed-subcommand
program.command(commandName);
// ok: dossier.js.blindspot.computed-subcommand
program.command('fixed');

const boundPath = '/bound';
// ruleid: dossier.js.blindspot.string-route
router.get(boundPath, handler);

// ruleid: dossier.js.blindspot.hook-wiring
export function useIndented() {
  return 3;
}
