import { useCart } from '../context';

export default function Home() {
  const cart = useCart();
  return <h1>Home {cart.length}</h1>;
}
