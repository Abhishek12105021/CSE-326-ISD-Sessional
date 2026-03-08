# YouTube Clone — Deployment & Customization Guide

> Companion documentation for the YouTube Clone React app.  
> See the main `README.md` for project overview and local setup.

---

## Table of Contents

1. [Deployment](#deployment)
   - [Option A — Vercel (Recommended)](#option-a--vercel-recommended)
   - [Option B — Netlify](#option-b--netlify)
   - [Option C — GitHub Pages](#option-c--github-pages)
   - [Option D — Any Static Host](#option-d--any-static-host)
2. [Feature Toggles — Remove What You Don't Want](#feature-toggles--remove-what-you-dont-want)
   - [Quick Toggle (1 minute)](#quick-toggle-1-minute)
   - [Permanent Removal (Clean Delete)](#permanent-removal-clean-delete)
   - [Removal Checklists](#removal-checklists)
3. [Environment & Build Info](#environment--build-info)

---

## Deployment

The app is a **static single-page application** (SPA). After building, the `dist/` folder contains plain HTML/CSS/JS files that can be hosted anywhere — no server required.

### Prerequisites

```bash
# Make sure dependencies are installed
npm install

# Create a production build
npm run build
```

This generates the `dist/` folder.

---

### Option A — Vercel (Recommended)

**Easiest method — zero config needed.**

1. Push your code to a GitHub / GitLab / Bitbucket repository.
2. Go to [vercel.com](https://vercel.com) and sign in with your Git provider.
3. Click **"Add New Project"** → Import your repository.
4. Vercel auto-detects Vite. Click **Deploy**.
5. Done! You get a live URL like `https://youtube-clone-xyz.vercel.app`.

The included `vercel.json` handles SPA routing automatically.

**Or deploy from terminal:**

```bash
# Install Vercel CLI (one time)
npm install -g vercel

# Deploy
vercel
```

---

### Option B — Netlify

1. Push your code to a Git repository.
2. Go to [netlify.com](https://www.netlify.com) and sign in.
3. Click **"Add new site"** → **"Import an existing project"**.
4. Select your repo. Netlify auto-detects the build settings from `netlify.toml`.
5. Click **Deploy site**.

The included `netlify.toml` handles:
- Build command: `npm run build`
- Publish directory: `dist`
- SPA fallback routing (all paths → `index.html`)

**Or drag-and-drop deploy:**

```bash
npm run build
```

Then drag the `dist/` folder onto [app.netlify.com/drop](https://app.netlify.com/drop).

---

### Option C — GitHub Pages

1. Create a GitHub repository and push your code.
2. Run the build:
   ```bash
   npm run build
   ```
3. Deploy the `dist/` folder to GitHub Pages using one of these methods:

   **Method 1 — GitHub Actions (automated):**
   
   Go to your repo → Settings → Pages → Source → **GitHub Actions**, then add the workflow below as `.github/workflows/deploy.yml`:

   ```yaml
   name: Deploy to GitHub Pages
   on:
     push:
       branches: [main]
   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with:
             node-version: 20
         - run: npm install
         - run: npm run build
         - uses: actions/upload-pages-artifact@v3
           with:
             path: dist
         - uses: actions/deploy-pages@v4
       permissions:
         pages: write
         id-token: write
       environment:
         name: github-pages
   ```

   **Method 2 — Manual:**
   
   ```bash
   npm install -g gh-pages
   npm run build
   gh-pages -d dist
   ```

> **Note:** The app uses `HashRouter` so all routes work on GitHub Pages without any extra server-side configuration. URLs will look like `https://user.github.io/youtube-clone/#/video/1`.

---

### Option D — Any Static Host

The `dist/` folder is completely self-contained. Upload it to any static file host:

- **Surge:** `npx surge dist`
- **Firebase Hosting:** `firebase deploy`
- **AWS S3 + CloudFront**
- **DigitalOcean App Platform**
- **Render** (static site)
- **Cloudflare Pages**

The app uses `HashRouter`, so routing works on all static hosts without any server configuration.

---

## Feature Toggles — Remove What You Don't Want

All features are controlled from a single config file:

📄 **`src/features.config.js`**

### Quick Toggle (1 minute)

Open `src/features.config.js` and set any feature to `false`:

```javascript
const features = {
  /* -------- Pages -------- */
  home: true,            // Home feed with video grid
  videoPlayer: true,     // /video/:id  — watch page
  channel: true,         // /channel/:id — channel page
  search: true,          // /search?q=   — search results
  shorts: true,          // Shorts placeholder route
  subscriptions: true,   // Subscriptions placeholder
  history: true,         // History placeholder
  trending: true,        // Trending placeholder

  /* -------- Components -------- */
  sidebar: true,         // Left sidebar navigation
  navbar: true,          // Top navigation bar

  /* -------- Home sub-features -------- */
  categoryChips: true,   // Filter chips on Home page
  shortsSection: true,   // Shorts carousel on Home page
};
```

**Example — Remove the Shorts section and Sidebar:**

```javascript
  shorts: false,          // ← turned off
  shortsSection: false,   // ← turned off
  sidebar: false,         // ← turned off
```

Save the file. The app will hot-reload and those features are gone.

---

### Permanent Removal (Clean Delete)

After toggling a feature off, you can optionally delete its files to keep the project clean. The app will still compile and run.

---

### Removal Checklists

#### Remove Search Page

1. Set `search: false` in `features.config.js`
2. Delete folder: `src/pages/Search/`
3. (Optional) Remove the search bar in `Navbar.jsx` if you don't need it

#### Remove Channel Page

1. Set `channel: false` in `features.config.js`
2. Delete folder: `src/pages/Channel/`

#### Remove Video Player Page

1. Set `videoPlayer: false` in `features.config.js`
2. Delete folder: `src/pages/VideoPlayer/`
3. Note: `VideoCard` links will lead to 404 — you may want to adjust `VideoCard.jsx`

#### Remove Shorts

1. Set `shorts: false` and `shortsSection: false` in `features.config.js`
2. The Shorts carousel on the Home page and the `/shorts` route are both removed

#### Remove Sidebar

1. Set `sidebar: false` in `features.config.js`
2. Delete folder: `src/components/Sidebar/`
3. The content area automatically expands to full width

#### Remove Navbar

1. Set `navbar: false` in `features.config.js`
2. Delete folder: `src/components/Navbar/`
3. Update `index.css` — remove or change `padding-top: 56px` from `.app`

#### Remove Category Chips (on Home)

1. Set `categoryChips: false` in `features.config.js`
2. All videos will show without filtering (the "All" category view)

#### Remove Placeholder Pages (Subscriptions / History / Trending)

1. Set the corresponding flag to `false`:
   ```javascript
   subscriptions: false,
   history: false,
   trending: false,
   ```
2. No files to delete — these are inline placeholder components in `App.jsx`
3. (Optional) Remove matching sidebar links in `Sidebar.jsx`

---

## Environment & Build Info

| Item | Value |
|------|-------|
| **Framework** | React 18 |
| **Build Tool** | Vite 5 |
| **Router** | React Router v6 (`HashRouter` for static hosting) |
| **Icons** | react-icons |
| **CSS** | Pure CSS (no framework) |
| **Node.js** | 18+ recommended |
| **Build Output** | `dist/` folder (static files) |

### Key Files

| File | Purpose |
|------|---------|
| `src/features.config.js` | Toggle features on/off |
| `src/App.jsx` | Main router — reads feature config |
| `src/data/sampleData.js` | All mock data (videos, comments, shorts) |
| `vite.config.js` | Build configuration |
| `vercel.json` | Vercel deployment config |
| `netlify.toml` | Netlify deployment config |
| `.gitignore` | Git ignore rules |

### Useful Commands

```bash
npm run dev           # Start dev server at localhost:3000
npm run build         # Create production build in dist/
npm run preview       # Preview production build locally
```

---

## Author

**CSE326 — Information System Design Sessional**  
Department of Computer Science & Engineering  
University Project — February 2026
