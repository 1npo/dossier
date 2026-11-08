import { create } from 'zustand';

// ruleid: dossier.js.state.db-connect
const prisma = new PrismaClient();
// ruleid: dossier.js.state.db-connect
const pool = new Pool({ max: 4 });
// ok: dossier.js.state.db-connect
const poolConfig = { max: 4 };

// ruleid: dossier.js.state.db-access
const users = await prisma.user.findMany();
// ruleid: dossier.js.state.db-access
const rows = await prisma.$queryRaw`select 1`;
// ruleid: dossier.js.state.db-access
pool.query('select 1');
// ok: dossier.js.state.db-access
cache.query('select 1');

// ruleid: dossier.js.state.global-state
const store = configureStore({ reducer });
// ruleid: dossier.js.state.global-state
globalThis.settings = {};
// ruleid: dossier.js.state.global-state
const useCart = create((set) => ({ items: [] }));
// ok: dossier.js.state.global-state
const local = { items: [] };

// ruleid: dossier.js.state.cache
const lru = new LRUCache({ max: 10 });
// ruleid: dossier.js.state.cache
const client = new QueryClient();
// ok: dossier.js.state.cache
const m = new Map();
