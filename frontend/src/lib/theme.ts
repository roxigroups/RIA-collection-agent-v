// Light or dark theme: saved on this browser, applied as <html data-theme="dark">.
// The script in layout.tsx applies the saved choice before the first paint.
export const THEME_KEY = 'ria.theme';

const listeners = new Set<() => void>();

export const subscribeTheme = (cb: () => void) => {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
};

export const isDarkTheme = () => document.documentElement.dataset.theme === 'dark';

export const setDarkTheme = (dark: boolean) => {
  if (dark) document.documentElement.dataset.theme = 'dark';
  else delete document.documentElement.dataset.theme;
  try {
    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light');
  } catch {
    // storage blocked: the theme still applies until the page is reloaded
  }
  listeners.forEach((cb) => cb());
};

export const THEME_SCRIPT = `try{if(localStorage.getItem('${THEME_KEY}')==='dark')document.documentElement.dataset.theme='dark'}catch(e){}`;
