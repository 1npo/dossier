import { Router } from 'express';
import { create, list } from './service';

const router = Router();
const map = new Map<string, string>();
const verb = 'get';
const path = '/dynamic';

router.get('/users', async (_req, res) => { // @ep-get
  res.json(await list());
});

router.post( // @ep-post
  '/users',
  async (req, res) => {
    if (!req.body) return res.status(404).end(); // @io-error
    res.status(201).json(await create(req.body));
  },
);

router[verb]('/x', (_req, res) => res.end()); // computed method: not detected
router.get(path, (_req, res) => res.end()); // @bs-route
map.get('users'); // @not-route

export default router;
