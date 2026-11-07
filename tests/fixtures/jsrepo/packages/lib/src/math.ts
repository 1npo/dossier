export function sum(a: number, b: number): number {
  return a + b;
}

export function twice(a: number): number {
  return a * 2;
}

export function hidden(): number { // @api-hidden
  return 0;
}
