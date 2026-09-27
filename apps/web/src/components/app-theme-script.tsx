import { APP_THEME_STORAGE_KEY } from "@/lib/app-theme";

/**
 * Sets `data-app-theme` on <html> synchronously, before first paint —
 * same technique next-themes itself uses for `class="dark"`, kept fully
 * independent of it. Without this, a returning visitor with a saved
 * visual theme would see one frame of the unthemed palette before React
 * hydrates and `AppThemeProvider` applies it.
 *
 * Server component: renders a plain <script>, no client JS bundle cost.
 */
export function AppThemeScript() {
  const inline = `(function(){try{var t=window.localStorage.getItem(${JSON.stringify(
    APP_THEME_STORAGE_KEY,
  )});var valid=["cosmic","mint","bloom","electric","sunset","arctic"];if(t&&valid.indexOf(t)!==-1){document.documentElement.setAttribute("data-app-theme",t);}}catch(e){}})();`;

  return <script dangerouslySetInnerHTML={{ __html: inline }} />;
}
