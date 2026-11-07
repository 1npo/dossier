import { prisma } from '../db';
import type { Port } from '../main'; // @import-up

export const defaultPort: Port = 3000;

export async function list() {
  return prisma.user.findMany(); // @io-db
}

export async function create(data: unknown) {
  const url = 'https://mail.example.com/send';
  await fetch(url, { timeout: 5 }); // @io-outbound
  try { // @fail-catch
    return await prisma.$transaction([prisma.user.create({ data: data as never })]); // @fail-tx
  } catch (err) {
    throw err;
  }
}
