import { list } from '../src/users/service';

jest.mock('../src/db'); // @test-mock

describe('users', () => {
  beforeEach(() => undefined);

  it('lists', async () => {
    await list();
  });

  test.todo('creates'); // @test-todo
});
