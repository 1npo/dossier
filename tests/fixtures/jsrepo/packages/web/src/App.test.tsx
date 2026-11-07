import { describe, expect, it, vi } from 'vitest';
import App from './App';

vi.mock('./context'); // @test-vi-mock

describe('App', () => {
  it('is defined', () => {
    expect(App).toBeDefined();
  });

  it.skip('renders later', () => undefined); // @test-skip
});
