import { Router } from 'express';
import users from './users/controller';

const api = Router();
api.use(users);

const router = Router();
router.use('/api', api); // @bs-mount

export default router;
