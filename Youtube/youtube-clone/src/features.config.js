/**
 * ============================================================
 *  FEATURE TOGGLES — Enable / Disable features from one place
 * ============================================================
 *
 * Set any value to `false` to completely remove that feature
 * from the app (the route won't be registered, and related
 * UI elements will be hidden).
 *
 * After toggling a feature OFF you can also safely delete
 * its folder — the app will still work. See DEPLOYMENT.md
 * for a full removal checklist.
 */

const features = {
  /* -------- Pages -------- */
  home: true,            // Home feed with video grid & category chips
  videoPlayer: true,     // /video/:id  — watch page with comments
  channel: true,         // /channel/:id — channel profile page
  search: true,          // /search?q=   — search results page
  shorts: true,          // Shorts placeholder route + Home section
  subscriptions: true,   // Subscriptions placeholder route
  history: true,         // History placeholder route
  trending: true,        // Trending placeholder route

  /* -------- Components -------- */
  sidebar: true,         // Left sidebar navigation
  navbar: true,          // Top navigation bar

  /* -------- Home sub-features -------- */
  categoryChips: true,   // Filter chips row on Home page
  shortsSection: true,   // Shorts carousel on Home page (only if shorts=true too)
};

export default features;
