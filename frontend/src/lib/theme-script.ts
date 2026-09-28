// Runs before paint (inlined in <head>) so there is no flash of the wrong theme.
// Reads a per-viewer localStorage preference; falls back to the OS setting via the CSS media
// query already defined in globals.css. Wrapped in try/catch per the browser-storage rules —
// this must never throw in a private window or when storage is blocked.
export const themeBootstrapScript = `
(function () {
  try {
    var stored = localStorage.getItem("talent-theme");
    if (stored === "light" || stored === "dark") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (e) {}
})();
`;
