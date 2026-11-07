import { createBrowserRouter } from 'react-router';
import App from './App';
import { paths } from './paths';

declare const prefix: string;

export const router = createBrowserRouter([
  { path: '/', element: <App /> }, // @ui-literal
  { path: paths.cart.path, element: <App /> }, // @ui-constant
  { path: prefix + '/x', element: <App /> }, // @ui-computed
  { path: '/home', lazy: () => import('./pages/Home') },
]);
