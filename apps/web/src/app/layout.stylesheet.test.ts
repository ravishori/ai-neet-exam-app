import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Recurrence guard for the "app renders unstyled" regression.
 *
 * The failure mode we've hit was NOT a source bug but a runtime one — a
 * corrupt `.next` dev cache that served the layout HTML with a valid
 * `<link>` to `/_next/static/css/app/layout.css`, while that CSS chunk
 * was missing from disk (HTTP 404). Fixing the runtime is the operator's
 * job (`rm -rf .next && npm run dev`); fixing the source-level failure
 * modes that *would* also produce an unstyled page is this test's job.
 *
 * If any of the assertions here fail, the app cannot pick up the Trinetra
 * design system at all — regardless of `.next` state.
 */

const HERE = dirname(fileURLToPath(import.meta.url));
// apps/web/ (i.e. src/app -> ../..)
const WEB_ROOT = resolve(HERE, "..", "..");
const LAYOUT = join(HERE, "layout.tsx");
const GLOBALS = join(HERE, "globals.css");

function read(path: string): string {
  return readFileSync(path, "utf8");
}

describe("app-layout / globals.css contract", () => {
  it("root layout.tsx imports ./globals.css exactly once", () => {
    const src = read(LAYOUT);
    const matches = src.match(/^\s*import\s+["']\.\/globals\.css["'];?\s*$/gm) ?? [];
    expect(matches.length, "root layout must import ./globals.css").toBe(1);
  });

  it("root layout.tsx wraps children in ThemeProvider + QueryProvider + TooltipProvider", () => {
    const src = read(LAYOUT);
    expect(src, "ThemeProvider mount missing").toMatch(/<ThemeProvider[\s>]/);
    expect(src, "QueryProvider mount missing").toMatch(/<QueryProvider[\s>]/);
    expect(src, "TooltipProvider mount missing").toMatch(/<TooltipProvider[\s>]/);
  });

  it("globals.css declares the load-bearing design tokens", () => {
    const src = read(GLOBALS);
    // Tailwind v4 entry
    expect(src, "@import \"tailwindcss\" missing").toMatch(/@import\s+["']tailwindcss["']/);
    // Semantic colour roles used by the whole DS
    for (const token of [
      "--background",
      "--foreground",
      "--primary",
      "--card",
      "--border",
      "--destructive",
      "--success",
      "--warning",
      "--ring",
    ]) {
      expect(src, `token ${token} missing in globals.css`).toContain(token);
    }
    // Typography utilities we lean on everywhere
    for (const utility of ["text-h1", "text-h2", "text-h3", "text-body", "text-caption", "text-meta", "text-question"]) {
      expect(src, `utility .${utility} missing in globals.css`).toContain(`@utility ${utility}`);
    }
    // Layout tokens
    for (const token of ["--content-max", "--touch-target-min", "--prose-measure"]) {
      expect(src, `layout token ${token} missing`).toContain(token);
    }
  });
});

/**
 * Optional: if a production build exists, verify at least one CSS chunk
 * was emitted. This catches the "empty .next/static/css/app/" corruption
 * mode too, but only runs when `.next/static/css` is present (i.e. after
 * `next build`). It is a no-op in dev-only workflows.
 */
describe("built CSS artefacts (post-build sanity)", () => {
  const cssDir = join(WEB_ROOT, ".next", "static", "css");
  it("if .next/static/css exists, it contains at least one non-empty .css file", () => {
    let entries: string[];
    try {
      entries = readdirSync(cssDir);
    } catch {
      return; // no build has been produced yet — skip silently
    }
    const cssFiles: string[] = [];
    for (const entry of entries) {
      const abs = join(cssDir, entry);
      if (statSync(abs).isDirectory()) {
        for (const child of readdirSync(abs)) {
          if (child.endsWith(".css")) cssFiles.push(join(abs, child));
        }
      } else if (entry.endsWith(".css")) {
        cssFiles.push(abs);
      }
    }
    expect(cssFiles.length, ".next/static/css exists but is empty").toBeGreaterThan(0);
    for (const file of cssFiles) {
      const size = statSync(file).size;
      expect(size, `${file} is empty`).toBeGreaterThan(0);
    }
  });
});
