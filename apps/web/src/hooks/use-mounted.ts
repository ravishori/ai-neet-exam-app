"use client";

import { useEffect, useState } from "react";

/**
 * True only after client mount — defer Base UI menus / theme-resolved UI so
 * SSR HTML never emits unstable `base-ui-*` trigger ids (FRONTEND-A12).
 */
export function useMounted() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}
