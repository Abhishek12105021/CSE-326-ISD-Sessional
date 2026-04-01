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
  const { isAuthenticated, session, guestId, region, getWatchedVideoIds } =
    useAuth();

  const [videos, setVideos] = useState([]);
  const [categories, setCategories] = useState(["All"]);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [appliedCategories, setAppliedCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const shownIds = useRef(new Set());
  const LIMIT = 30;

  const dbCategories = categories.filter((cat) => cat !== "All");
  const allCategoriesSelected =
    dbCategories.length > 0 &&
    selectedCategories.length === dbCategories.length &&
    dbCategories.every((cat) => selectedCategories.includes(cat));
  const hasAppliedCategoryFilter = appliedCategories.length > 0;

  // Fetch categories once on mount
  useEffect(() => {
    apiService
      .get(API_ENDPOINTS.CATEGORIES)
      .then((data) => {
        const incoming = data?.categories || [];
        const uniqueDbCategories = Array.from(
          new Set(incoming.filter((cat) => cat && cat !== "All")),
        );
        setCategories(["All", ...uniqueDbCategories]);
      })
      .catch(() => {}); // silently keep default "All" on failure
  }, []);

  // Fetch initial feed when auth state or region changes
  const fetchFeed = useCallback(async () => {
    setLoading(true);
    shownIds.current = new Set();
    try {
      let data;
      if (isAuthenticated && session?.access_token) {
        data = await apiService
          .withAuth(session.access_token)
          .get(`${API_ENDPOINTS.FEED}?region=${region}&limit=${LIMIT}`);
      } else {
        data = await apiService.post(API_ENDPOINTS.GUEST_FEED, {
          guest_uuid: guestId,
          region: region,
          watched_video_ids: getWatchedVideoIds(),
          limit: LIMIT,
        });
      }
      const fetched = data?.videos || [];
      fetched.forEach((v) => shownIds.current.add(v.id));
      setVideos(fetched);
      setHasMore(fetched.length > 0);
      setAppliedCategories([]);
      setSelectedCategories([]);
    } catch (err) {
      console.error("[Home] Failed to fetch feed:", err);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, session, guestId, region, getWatchedVideoIds, LIMIT]);

  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  const toggleCategorySelection = useCallback(
    (category) => {
      setSelectedCategories((prev) => {
        if (category === "All") {
          return dbCategories;
        }

        if (prev.includes(category)) {
          return prev.filter((cat) => cat !== category);
        }

        return [...prev, category];
      });
    },
    [dbCategories],
  );

  const removeCategorySelection = useCallback((category) => {
    setSelectedCategories((prev) => prev.filter((cat) => cat !== category));
  }, []);

  const applyCategorySelection = useCallback(async () => {
    if (selectedCategories.length === 0) return;

    setLoading(true);
    shownIds.current = new Set();

    try {
      const data = await apiService.post(API_ENDPOINTS.SEARCH_BY_CATEGORY, {
        categories: selectedCategories,
        excluded_video_ids: [],
        limit: LIMIT,
      });

      const fetched = data?.videos || [];
      fetched.forEach((v) => shownIds.current.add(v.id));

      setVideos(fetched);
      setAppliedCategories(selectedCategories);
      setHasMore(fetched.length > 0);
    } catch (err) {
      console.error("[Home] Failed to apply category search:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedCategories, LIMIT]);

  // Load more videos (infinite scroll)
  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const excludedIds = Array.from(shownIds.current);
      let data;

      if (hasAppliedCategoryFilter) {
        data = await apiService.post(API_ENDPOINTS.SEARCH_BY_CATEGORY_RELOAD, {
          categories: appliedCategories,
          excluded_video_ids: excludedIds,
          limit: LIMIT,
        });
      } else if (isAuthenticated && session?.access_token) {
        data = await apiService
          .withAuth(session.access_token)
          .post(API_ENDPOINTS.FEED_RELOAD, {
            excluded_video_ids: excludedIds,
            limit: LIMIT,
          });
      } else {
        data = await apiService.post(API_ENDPOINTS.GUEST_RELOAD, {
          guest_uuid: guestId,
          region: region,
          watched_video_ids: getWatchedVideoIds(),
          excluded_video_ids: excludedIds,
          limit: LIMIT,
        });
      }
      const fetched = data?.videos || [];
      fetched.forEach((v) => shownIds.current.add(v.id));
      setVideos((prev) => [...prev, ...fetched]);

      if (hasAppliedCategoryFilter && typeof data?.has_more === "boolean") {
        setHasMore(data.has_more);
      } else {
        setHasMore(fetched.length > 0);
      }
    } catch (err) {
      console.error("[Home] Failed to load more:", err);
    } finally {
      setLoadingMore(false);
    }
  }, [
    loadingMore,
    hasMore,
    hasAppliedCategoryFilter,
    appliedCategories,
    isAuthenticated,
    session,
    guestId,
    region,
    getWatchedVideoIds,
    LIMIT,
  ]);

  // Scroll listener for infinite scroll
  useEffect(() => {
    const handleScroll = () => {
      const nearBottom =
        window.innerHeight + window.scrollY >=
        document.documentElement.scrollHeight - 600;
      if (nearBottom) loadMore();
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [loadMore]);

  const showShorts =
    features.shorts && features.shortsSection && !hasAppliedCategoryFilter;

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
              className={`category-pill ${
                cat === "All"
                  ? allCategoriesSelected
                    ? "category-pill--active"
                    : ""
                  : selectedCategories.includes(cat)
                    ? "category-pill--active"
                    : ""
              }`}
              onClick={() => toggleCategorySelection(cat)}
            >
              <span className="category-pill__label">{cat}</span>
              {cat !== "All" && selectedCategories.includes(cat) && (
                <span
                  className="category-pill__remove"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeCategorySelection(cat);
                  }}
                  aria-label={`Remove ${cat}`}
                >
                  ×
                </span>
              )}
            </button>
          ))}

          {selectedCategories.length > 0 && (
            <button
              className="category-pill category-pill--active category-pill--confirm"
              onClick={applyCategorySelection}
            >
              Confirm
            </button>
          )}
        </div>
      )}

      {hasAppliedCategoryFilter && (
        <div className="home__active-filter">
          Showing categories: {appliedCategories.join(", ")}
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
        {videos.map((video) => (
          <VideoCard key={video.id} video={video} />
        ))}
      </div>

      {videos.length === 0 && !loading && (
        <div style={{ textAlign: "center", padding: "48px", color: "#606060" }}>
          <h3>
            {hasAppliedCategoryFilter
              ? `No videos found for ${appliedCategories.join(", ")}`
              : "No videos found"}
          </h3>
          <p>
            {hasAppliedCategoryFilter
              ? "Try changing your selected categories"
              : "Please refresh and try again"}
          </p>
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
