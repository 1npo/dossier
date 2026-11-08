declare const container: { bind(x: unknown): void };

class Mailer {}

export async function load(name: string) {
  const mod = await import(`./${name}`); // @bs-import
  const dyn = require(name); // @bs-require
  container.bind(Mailer); // @bs-di
  return [mod, dyn];
}
