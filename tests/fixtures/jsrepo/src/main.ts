import express from 'express';
import routes from './routes';

export type Port = number;

const app = express();
app.use(routes);
app.get('/', (_req, res) => res.send('shop')); // @ep-root
const port: Port = Number(process.env.PORT ?? 3000); // @io-env
app.listen(port, () => { // @ep-listen
  console.info(`listening on ${port}`); // @io-log
});

export default app;
