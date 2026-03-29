import React, { useState, useEffect, useCallback, useRef } from "react";
import { VideoCard } from "../../components";
import { shortsData } from "../../data/sampleData";
import { SiYoutubeshorts } from "react-icons/si";
import { features } from "../../config";
import { useAuth } from "../../context";
import { apiService } from "../../services";
import { API_ENDPOINTS } from "../../config";
import "./Home.css";

const Home = () => {
  const { isAuthenticated, session, guestId, region, getWatchedVideoIds } = useAuth();

  const [videos, setVideos] = useState([]);
  const [categories, setCategories] = useState(["All"]);
  const [activeCategory, setActiveCategory] = useState("All");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const shownIds = useRef(new Set());

  // Fetch categories once on mount
  useEffect(() => {
    apiService.get(API_ENDPOINTS.CATEGORIES)
      .then(data => setCategories(["All", ...(data.categories || [])]))
      .catch(() => {}); // silently keep default "All" on failure
  }, []);

  // Fetch initial feed when auth state or region changes
  const fetchFeed = useCallback(async () => {
    setLoading(true);
    shownIds.current = new Set();
    try {
      let data;
      if (isAuthenticated && session?.access_token) {
        data = await apiService.withAuth(session.access_token).get(
          `${API_ENDPOINTS.FEED}?region=${region}&limit=30`
        );
      } else {
        data = await apiService.post(API_ENDPOINTS.GUEST_FEED, {
          guest_uuid: guestId,
          region: region,
          watched_video_ids: getWatchedVideoIds(),
          limit: 30,
        });
      }
      const fetched = data?.videos || [];
      fetched.forEach(v => shownIds.current.add(v.id));
      setVideos(fetched);
      setHasMore(fetched.length > 0);
    } catch (err) {
      console.error("[Home] Failed to fetch feed:", err);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, session, guestId, region, getWatchedVideoIds]);

  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  // Load more videos (infinite scroll)
  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const excludedIds = Array.from(shownIds.current);
      let data;
      if (isAuthenticated && session?.access_token) {
        data = await apiService.withAuth(session.access_token).post(
          API_ENDPOINTS.FEED_RELOAD,
          { excluded_video_ids: excludedIds, limit: 30 }
        );
      } else {
        data = await apiService.post(API_ENDPOINTS.GUEST_RELOAD, {
          guest_uuid: guestId,
          region: region,
          watched_video_ids: getWatchedVideoIds(),
          excluded_video_ids: excludedIds,
          limit: 30,
        });
      }
      const fetched = data?.videos || [];
      fetched.forEach(v => shownIds.current.add(v.id));
      setVideos(prev => [...prev, ...fetched]);
      setHasMore(fetched.length > 0);
    } catch (err) {
      console.error("[Home] Failed to load more:", err);
    } finally {
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, isAuthenticated, session, guestId, region, getWatchedVideoIds]);

  // Scroll listener for infinite scroll
  useEffect(() => {
    const handleScroll = () => {
      const nearBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 600;
      if (nearBottom) loadMore();
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [loadMore]);

  // Client-side category filter
  const filteredVideos =
    activeCategory === "All"
      ? videos
      : videos.filter((v) => v.category === activeCategory);

  const showShorts = features.shorts && features.shortsSection && activeCategory === "All";

  if (loading) {
    return (
      <div className="home">
        <div style={{ textAlign: "center", padding: "80px", color: "#606060" }}>
          <div className="loading-spinner" />
          <p style={{ marginTop: "16px" }}>Loading videos…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="home">
      {/* Category Pills */}
      {features.categoryChips && (
        <div className="category-bar">
          {categories.map((cat) => (
            <button
              key={cat}
              className={`category-pill ${activeCategory === cat ? "category-pill--active" : ""}`}
              onClick={() => setActiveCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* Shorts Section */}
      {showShorts && (
        <>
          <div className="shorts-section">
            <div className="shorts-section__header">
              <SiYoutubeshorts className="shorts-section__icon" />
              <h2 className="shorts-section__title">Shorts</h2>
            </div>
            <div className="shorts-section__grid">
              {shortsData.map((short) => (
                <div key={short.id} className="shorts-card">
                  <img
                    className="shorts-card__thumbnail"
                    src={short.thumbnail}
                    alt={short.title}
                    loading="lazy"
                  />
                  <div className="shorts-card__overlay">
                    <p className="shorts-card__title">{short.title}</p>
                    <p className="shorts-card__views">{short.views} views</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <hr className="section-divider" />
        </>
      )}

      {/* Video Grid */}
      <div className="home__video-grid">
        {filteredVideos.map((video) => (
          <VideoCard key={video.id} video={video} />
        ))}
      </div>

      {filteredVideos.length === 0 && !loading && (
        <div style={{ textAlign: "center", padding: "48px", color: "#606060" }}>
          <h3>No videos found for "{activeCategory}"</h3>
          <p>Try selecting a different category</p>
        </div>
      )}

      {loadingMore && (
        <div style={{ textAlign: "center", padding: "24px", color: "#606060" }}>
          <div className="loading-spinner" />
        </div>
      )}

      {!hasMore && videos.length > 0 && (
        <div style={{ textAlign: "center", padding: "24px", color: "#606060" }}>
          <p>You've reached the end</p>
        </div>
      )}
    </div>
  );
};

export default Home;
