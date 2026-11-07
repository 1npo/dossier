export { sum } from './math'; // @api-reexport
export { twice as double } from './math'; // @api-rename
export * from './barrel';

export const version = '1'; // @api-own
