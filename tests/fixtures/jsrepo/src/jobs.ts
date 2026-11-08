import { Worker } from 'bullmq';
import cron from 'node-cron';

cron.schedule('0 * * * *', () => undefined); // @ep-cron
new Worker('mail', async () => undefined); // @ep-queue
