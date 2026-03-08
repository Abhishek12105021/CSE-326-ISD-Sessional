# YouTube Clone — React UI

> **CSE326 Information System Design Sessional — University Project**

A pixel-perfect YouTube UI clone built entirely with React + Vite. No CSS frameworks — pure CSS only, closely matching the real YouTube interface.

---

## What Was Built

### Pages

| Page | Route | What's Inside |
|------|-------|---------------|
| **Home** | `/` | Category filter chips, YouTube Shorts horizontal carousel, responsive video grid (16 sample videos) |
| **Video Player** | `/video/:id` | Video thumbnail player, progress bar, like/dislike toggle, subscribe toggle, collapsible description, nested comments with replies, recommended videos sidebar |
| **Channel** | `/channel/:channelId` | Channel banner image, large avatar, subscriber count, tab navigation (Home / Videos / Shorts / Live / Playlists / Community / About), channel video grid |
| **Search** | `/search?q=...` | Horizontal search result cards (matches title, channel name, category), filter button |
| **Shorts / Subscriptions / Trending / History** | Various | Placeholder pages (ready to extend) |

### Components

| Component | Location | Description |
|-----------|----------|-------------|
| `Navbar` | `src/components/Navbar/` | Fixed top bar with YouTube logo, search input (press Enter to search), voice icon, notifications badge, user avatar |
| `Sidebar` | `src/components/Sidebar/` | Collapsible left sidebar (hamburger toggle), Home / Shorts / Subscriptions / You section / Explore / Settings |
| `VideoCard` | `src/components/VideoCard/` | Thumbnail with LIVE badge or duration, channel avatar, title (2-line clamp), views & timestamp |

### Data

- `src/data/sampleData.js` — 16 realistic videos, 6 shorts, 5 comments with nested replies, 16 filter categories, all using public placeholder images (no assets needed)

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| React 18 | UI framework |
| Vite | Build tool & dev server |
| React Router v6 | Client-side routing |
| React Icons | All icons (MdVerified, AiOutlineLike, BsYoutube, etc.) |
| Pure CSS | Styling (no Tailwind / Bootstrap) |

---

## Project Structure

```
youtube-clone/
├── public/
│   └── vite.svg                    ← YouTube-style favicon
├── src/
│   ├── components/
│   │   ├── Navbar/
│   │   │   ├── Navbar.jsx
│   │   │   └── Navbar.css
│   │   ├── Sidebar/
│   │   │   ├── Sidebar.jsx
│   │   │   └── Sidebar.css
│   │   └── VideoCard/
│   │       ├── VideoCard.jsx
│   │       └── VideoCard.css
│   ├── pages/
│   │   ├── Home/
│   │   │   ├── Home.jsx
│   │   │   └── Home.css
│   │   ├── VideoPlayer/
│   │   │   ├── VideoPlayer.jsx
│   │   │   └── VideoPlayer.css
│   │   ├── Channel/
│   │   │   ├── Channel.jsx
│   │   │   └── Channel.css
│   │   └── Search/
│   │       ├── Search.jsx
│   │       └── Search.css
│   ├── data/
│   │   └── sampleData.js           ← All sample videos, comments, shorts
│   ├── App.jsx                     ← Router + layout wrapper
│   ├── main.jsx                    ← React entry point
│   └── index.css                   ← Global styles & layout
├── index.html
├── package.json
├── vite.config.js
└── README.md
```

---

## ⚡ Step-by-Step Setup Instructions

Follow these steps **in order** to get the project running on your machine.

---

### Step 1 — Install Node.js

Node.js is required to run the project. You currently don't have it installed.

1. Go to: **https://nodejs.org/**
2. Download the **LTS version** (the left green button — e.g. "22.x.x LTS")
3. Run the installer — keep all default options and click **Next** until it finishes
4. When asked _"Install additional tools for Node.js"_, check that box and let it run
5. **Restart your computer** after installation

To verify it worked, open a **new** PowerShell window and run:
```powershell
node --version
npm --version
```
Both should print version numbers (e.g. `v22.x.x` and `10.x.x`).

---

### Step 2 — Open the Project Folder in Terminal

Open PowerShell and navigate to the project:

```powershell
cd "c:\D drive\L3-T2\CSE326 Information System Design Sessional\youtube-clone"
```

---

### Step 3 — Install Dependencies

This downloads all the required packages (React, Vite, React Router, React Icons):

```powershell
npm install
```

> This will create a `node_modules` folder. It may take 1–2 minutes — that's normal.

---

### Step 4 — Start the Development Server

```powershell
npm run dev
```

You will see output like:
```
  VITE v5.x.x  ready in 300 ms

  ➜  Local:   http://localhost:3000/
```

---

### Step 5 — Open in Browser

Open your browser and go to:

**http://localhost:3000**

The YouTube Clone UI should be running! 🎉

---

### Step 6 — Open in VS Code (Optional but Recommended)

To edit the project in VS Code:

```powershell
code .
```

(Run this from inside the `youtube-clone` folder)

---

## How to Stop the Server

Press `Ctrl + C` in the terminal where `npm run dev` is running.

---

## How to Build for Production

When you're ready to submit or deploy:

```powershell
npm run build
```

This creates a `dist/` folder with optimized static files.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `npm` not recognized | Restart PowerShell/computer after installing Node.js |
| Port 3000 already in use | Change port in `vite.config.js` (e.g. `port: 3001`) |
| Images not loading | Requires internet connection (images are from picsum.photos) |
| `node_modules` missing | Run `npm install` again |

---

## Author

**CSE326 — Information System Design Sessional**  
Department of Computer Science & Engineering  
University Project — February 2026
