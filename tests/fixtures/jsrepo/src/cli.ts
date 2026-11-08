import { program } from 'commander';

program.command('sync').action(() => undefined); // @ep-cli
program.parse();

export function fail(): never {
  process.exit(1); // @io-exit
}
