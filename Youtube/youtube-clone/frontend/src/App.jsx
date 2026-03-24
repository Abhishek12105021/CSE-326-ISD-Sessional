import React, { useState } from "react";
import { HashRouter as Router, Routes, Route } from "react-router-dom";
import { features } from "./config";
import { AuthProvider } from "./context";
import { Navbar, Sidebar } from "./components";
import { SignIn } from "./pages";

const Home         = features.home        ? React.lazy(() => import("./pages/Home/Home"))               : null;
const VideoPlayer  = features.videoPlayer ? React.lazy(() => import("./pages/VideoPlayer/VideoPlayer")) : null;
const Channel      = features.channel     ? React.lazy(() => import("./pages/Channel/Channel"))         : null;
const Search       = features.search      ? React.lazy(() => import("./pages/Search/Search"))           : null;

/* Main app layout with navbar and sidebar */
const AppLayout = ({ sidebarCollapsed, toggleSidebar }) => {
  /* Compute layout classes depending on which components are enabled */
  const contentClasses = [
    "app__content",
    features.sidebar && sidebarCollapsed ? "app__content--collapsed" : "",
    !features.sidebar ? "app__content--no-sidebar" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="app">
      {features.navbar && <Navbar toggleSidebar={toggleSidebar} />}
      {features.sidebar && <Sidebar isCollapsed={sidebarCollapsed} />}

      <main className={contentClasses}>
        <React.Suspense fallback={<PageLoader />}>
          <Routes>
            {/* ── Core pages ── */}
            {features.home && (
              <Route path="/" element={<Home />} />
            )}
            {features.videoPlayer && (
              <Route path="/video/:id" element={<VideoPlayer />} />
            )}
            {features.channel && (
              <Route path="/channel/:channelId" element={<Channel />} />
            )}
            {features.search && (
              <Route path="/search" element={<Search />} />
            )}

            {/* ── Placeholder pages (toggle individually) ── */}
            {features.shorts && (
              <Route
                path="/shorts"
                element={<PlaceholderPage title="Shorts" description="YouTube Shorts will appear here" />}
              />
            )}
            {features.subscriptions && (
              <Route
                path="/subscriptions"
                element={<PlaceholderPage title="Subscriptions" description="Your subscribed channels' latest videos" />}
              />
            )}
            {features.history && (
              <Route
                path="/history"
                element={<PlaceholderPage title="History" description="Your watch history will appear here" />}
              />
            )}
            {features.trending && (
              <Route
                path="/trending"
                element={<PlaceholderPage title="Trending" description="See what's trending on YouTube" />}
              />
            )}

            {/* ── 404 fallback ── */}
            <Route
              path="*"
              element={<PlaceholderPage title="Page Not Found" description="This page isn't available. Try searching for something else." />}
            />
          </Routes>
        </React.Suspense>
      </main>
    </div>
  );
};

const App = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => !prev);
  };

  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Sign in page - standalone without navbar/sidebar */}
          <Route path="/signin" element={<SignIn />} />

          {/* All other routes with main layout */}
          <Route
            path="/*"
            element={
              <AppLayout
                sidebarCollapsed={sidebarCollapsed}
                toggleSidebar={toggleSidebar}
              />
            }
          />
        </Routes>
      </Router>
    </AuthProvider>
  );
};

/* Small spinner shown while lazy-loaded pages are being fetched */
const PageLoader = () => (
  <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh" }}>
    <div style={{ width: 40, height: 40, border: "3px solid #e5e5e5", borderTopColor: "#ff0000", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
  </div>
);

/* Simple placeholder for routes not yet fully implemented */
const PlaceholderPage = ({ title, description }) => (
  <div
    style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: "60vh",
      color: "#606060",
    }}
  >
    <h1 style={{ fontSize: "24px", marginBottom: "8px", color: "#0f0f0f" }}>
      {title}
    </h1>
    <p style={{ fontSize: "14px" }}>{description}</p>
  </div>
);

export default App;
