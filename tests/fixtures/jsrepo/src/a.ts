import { b } from './b'; // @cycle-a

export function a(): number {
  return b() + 1;
}
