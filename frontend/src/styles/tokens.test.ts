/// <reference types="node" />
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

// Read from disk: vitest stubs CSS imports (even ?raw) unless css processing is on.
const css = readFileSync(new URL('./tokens.css', import.meta.url), 'utf8');

function block(selector: string): string[] {
  const start = css.indexOf(selector);
  expect(start, `missing ${selector}`).toBeGreaterThan(-1);
  const open = css.indexOf('{', start);
  const close = css.indexOf('}', open);
  return css
    .slice(open + 1, close)
    .split(';')
    .map((d) => d.replace(/\/\*.*?\*\//gs, '').trim())
    .filter(Boolean)
    .sort();
}

describe('tokens.css', () => {
  it('the auto-light and explicit-light blocks are identical', () => {
    const auto = block(":root:not([data-theme='dark'])");
    const explicit = block(":root[data-theme='light']");
    expect(auto.length).toBeGreaterThan(10);
    expect(explicit).toEqual(auto);
  });
});
