export let current: string | null = null; // @state-let
const cache = new Map<string, number>(); // @state-map
const NAMES = { a: 1 };

export function remember(key: string): number {
  cache.set(key, 1);
  current = key;
  return NAMES.a;
}
