import { RouterProvider } from 'react-router';
import { CartProvider } from './context';
import { router } from './router';

export const root = (
  <CartProvider>
    <RouterProvider router={router} />
  </CartProvider>
);
