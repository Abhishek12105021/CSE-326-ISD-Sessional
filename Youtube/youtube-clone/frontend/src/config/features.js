/**
 * Feature Toggles - Enable/Disable features from one place
 * Set any value to `false` to remove that feature from the app
 */

const features = {
  // Pages
  home: true,
  videoPlayer: true,
  channel: true,
  search: true,
  shorts: true,
  subscriptions: true,
  history: true,
  trending: true,

  // Components
  sidebar: true,
  navbar: true,

  // Home sub-features
  categoryChips: true,
  shortsSection: true,
};

export default features;
