import { a } from './a'; // @cycle-b

export function b(): number {
  return a === undefined ? 0 : 1;
}
