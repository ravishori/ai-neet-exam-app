export const DEFAULT_AFTER_LOGIN = "/student/dashboard";

/**
 * Post-login destination from the `?next=` query parameter.
 *
 * Only same-origin relative paths are allowed, so a crafted link such as
 * `/login?next=https://evil.example` (or protocol-relative `//evil.example`,
 * `/\evil.example`) cannot send a freshly signed-in user off-site.
 */
export function safeNextPath(next: string | null | undefined): string {
  if (!next) return DEFAULT_AFTER_LOGIN;

  const isRelativePath =
    next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\");
  // Control characters (e.g. tab/newline) can be stripped by URL parsers and
  // turn "/\t/evil" into "//evil".
  const hasControlChars = /[\u0000-\u001f\u007f]/.test(next);

  return isRelativePath && !hasControlChars ? next : DEFAULT_AFTER_LOGIN;
}
