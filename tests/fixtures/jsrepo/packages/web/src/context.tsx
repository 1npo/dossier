import { createContext, useContext, type ReactNode } from 'react';

export const CartContext = createContext<number[]>([]); // @bs-context

export function useCart() { // @bs-hook
  return useContext(CartContext);
}

export function CartProvider({ children }: { children: ReactNode }) {
  return <CartContext.Provider value={[]}>{children}</CartContext.Provider>;
}
