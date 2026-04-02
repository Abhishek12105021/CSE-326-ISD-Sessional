import React, { useState, useEffect, useCallback, useRef } from "react";
import { VideoCard } from "../../components";
import { BsSliders } from "react-icons/bs";
import { features } from "../../config";
import { useAuth } from "../../context";
import { apiService } from "../../services";
import { API_ENDPOINTS } from "../../config";
import "./Home.css";

const HARDCODED_REGIONS = [
  "US",
  "GB",
  "IN",
  "CA",
  "DE",
  "FR",
  "JP",
  "KR",
  "MX",
  "RU",
];

const LIMIT = 30;


const Home = () => {
  const { isAuthenticated, session, guestId, region, getWatchedVideoIds } =
    useAuth();

  const [videos, setVideos] = useState([]);
  const [categories, setCategories] = useState(["All"]);

  // Top bar: instant single-category filter
  const [activeQuickCategory, setActiveQuickCategory] = useState(null);

  // Dropdown: temp selections (not applied until Apply is clicked)
  const [dropdownCategories, setDropdownCategories] = useState([]);
  const [dropdownRegions, setDropdownRegions] = useState([]);

  // Applied filter state (drives API calls and UI indicators)
  const [appliedCategories, setAppliedCategories] = useState([]);
  const [appliedRegions, setAppliedRegions] = useState([]);

  const [regions, setRegions] = useState([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 });
  const [categorySearch, setCategorySearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const shownIds = useRef(new Set());
  const dropdownTriggerRef = useRef(null);
  const dropdownRef = useRef(null);

  const dbCategories = categories.filter((cat) => cat !== "All");
  const filteredDropdownCategories = categorySearch
    ? dbCategories.filter((cat) =>
        cat.toLowerCase().includes(categorySearch.toLowerCase()),
      )
    : dbCategories;
  const hasAppliedCategoryFilter = appliedCategories.length > 0;
  const hasAppliedRegionFilter = appliedRegions.length > 0;
  const hasAnyAppliedFilter = hasAppliedCategoryFilter || hasAppliedRegionFilter;
  const totalAppliedCount = appliedCategories.length + appliedRegions.length;

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
      .catch(() => {});
  }, []);

  // Fetch regions once on mount (frontend hardcoded source)
  useEffect(() => {
    setRegions(HARDCODED_REGIONS);
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
      setActiveQuickCategory(null);
      setAppliedCategories([]);
      setAppliedRegions([]);
      setDropdownCategories([]);
      setDropdownRegions([]);
    } catch (err) {
      console.error("[Home] Failed to fetch feed:", err);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, session, guestId, region, getWatchedVideoIds]);

  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  // Dropdown position tracking
  const updateDropdownPosition = useCallback(() => {
    const trigger = dropdownTriggerRef.current;
    if (!trigger) return;

    const rect = trigger.getBoundingClientRect();
    const estimatedWidth = 560;
    const viewportPadding = 12;
    const maxLeft = window.innerWidth - estimatedWidth - viewportPadding;
    const safeLeft = Math.max(viewportPadding, Math.min(rect.left, maxLeft));

    setDropdownPosition({
      top: rect.bottom + 10,
      left: safeLeft,
    });
  }, []);

  useEffect(() => {
    if (!isDropdownOpen) return;

    updateDropdownPosition();

    const handleViewportChange = () => updateDropdownPosition();
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);

    return () => {
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [isDropdownOpen, updateDropdownPosition]);

  // Clear category search when dropdown closes
  useEffect(() => {
    if (!isDropdownOpen) setCategorySearch("");
  }, [isDropdownOpen]);

  useEffect(() => {
    if (!isDropdownOpen) return;

    const handleOutsideClick = (event) => {
      const target = event.target;
      if (
        dropdownRef.current?.contains(target) ||
        dropdownTriggerRef.current?.contains(target)
      ) {
        return;
      }
      setIsDropdownOpen(false);
    };

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [isDropdownOpen]);

  // Quick single-category click — instant filter
  const handleQuickCategoryClick = useCallback(
    async (category) => {
      setIsDropdownOpen(false);

      if (category === "All" || activeQuickCategory === category) {
        // Reset to default feed
        setActiveQuickCategory(null);
        setAppliedCategories([]);
        setAppliedRegions([]);
        setDropdownCategories([]);
        setDropdownRegions([]);
        await fetchFeed();
        return;
      }

      setActiveQuickCategory(category);
      setAppliedCategories([category]);
      setAppliedRegions([]);
      setDropdownCategories([]);
      setDropdownRegions([]);
      setLoading(true);
      shownIds.current = new Set();

      try {
        const data = await apiService.post(API_ENDPOINTS.FILTER_HOMEFEED, {
          categories: [category],
          regions: [],
          excluded_video_ids: [],
          limit: LIMIT,
        });
        const fetched = data?.videos || [];
        fetched.forEach((v) => shownIds.current.add(v.id));
        setVideos(fetched);
        setHasMore(fetched.length > 0);
      } catch (err) {
        console.error("[Home] Failed to apply quick category filter:", err);
      } finally {
        setLoading(false);
      }
    },
    [activeQuickCategory, fetchFeed],
  );

  // Dropdown: multi-category toggle
  const toggleDropdownCategory = useCallback(
    (category) => {
      setDropdownCategories((prev) => {
        if (category === "All") {
          const allSelected =
            dbCategories.length > 0 &&
            prev.length === dbCategories.length &&
            dbCategories.every((cat) => prev.includes(cat));
          return allSelected ? [] : [...dbCategories];
        }
        if (prev.includes(category)) {
          return prev.filter((cat) => cat !== category);
        }
        return [...prev, category];
      });
    },
    [dbCategories],
  );

  // Dropdown: region toggle
  const toggleDropdownRegion = useCallback((regionCode) => {
    setDropdownRegions((prev) => {
      if (prev.includes(regionCode)) {
        return prev.filter((r) => r !== regionCode);
      }
      return [...prev, regionCode];
    });
  }, []);

  // Dropdown: apply button
  const applyDropdownFilters = useCallback(async () => {
    const cats = [...dropdownCategories];
    const regs = [...dropdownRegions];

    setIsDropdownOpen(false);

    if (cats.length === 0 && regs.length === 0) {
      setActiveQuickCategory(null);
      await fetchFeed();
      return;
    }

    setActiveQuickCategory(null);
    setLoading(true);
    shownIds.current = new Set();

    try {
      const data = await apiService.post(API_ENDPOINTS.FILTER_HOMEFEED, {
        categories: cats,
        regions: regs,
        excluded_video_ids: [],
        limit: LIMIT,
      });
      const fetched = data?.videos || [];
      fetched.forEach((v) => shownIds.current.add(v.id));
      setVideos(fetched);
      setAppliedCategories(cats);
      setAppliedRegions(regs);
      setHasMore(fetched.length > 0);
    } catch (err) {
      console.error("[Home] Failed to apply dropdown filters:", err);
    } finally {
      setLoading(false);
    }
  }, [dropdownCategories, dropdownRegions, fetchFeed]);

  const loadPersonalizedFeed = useCallback(async () => {
    setIsDropdownOpen(false);
    await fetchFeed();
  }, [fetchFeed]);

  // Load more videos (infinite scroll)
  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const excludedIds = Array.from(shownIds.current);
      let data;

      if (hasAnyAppliedFilter) {
        data = await apiService.post(API_ENDPOINTS.FILTER_HOMEFEED_RELOAD, {
          categories: appliedCategories,
          regions: appliedRegions,
          excluded_video_ids: excludedIds,
          limit: LIMIT,
        });
      } else if (isAuthenticated && session?.access_token) {
        data = await apiService
          .withAuth(session.access_token)
          .post(`${API_ENDPOINTS.FEED_RELOAD}?region=${region}`, {
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

      if (hasAnyAppliedFilter && typeof data?.has_more === "boolean") {
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
    hasAnyAppliedFilter,
    appliedCategories,
    appliedRegions,
    isAuthenticated,
    session,
    guestId,
    region,
    getWatchedVideoIds,
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
      {/* Category Bar */}
      {features.categoryChips && (
        <>
          <div className="category-bar">
            {/* Advanced Filters dropdown trigger — icon only */}
            <button
              ref={dropdownTriggerRef}
              className={`filter-trigger-btn ${isDropdownOpen ? "filter-trigger-btn--open" : ""} ${hasAnyAppliedFilter && !activeQuickCategory ? "filter-trigger-btn--active" : ""}`}
              onClick={() => setIsDropdownOpen((prev) => !prev)}
              title="Advanced Filters"
            >
              <BsSliders className="filter-trigger-btn__icon" />
              {hasAnyAppliedFilter && !activeQuickCategory && (
                <span className="filter-trigger-btn__badge">
                  {totalAppliedCount}
                </span>
              )}
            </button>

            {/* Quick single-category pills */}
            {categories.map((cat) => (
              <button
                key={cat}
                className={`category-pill ${
                  cat === "All"
                    ? !activeQuickCategory && !hasAnyAppliedFilter
                      ? "category-pill--active"
                      : ""
                    : activeQuickCategory === cat
                      ? "category-pill--active"
                      : ""
                }`}
                onClick={() => handleQuickCategoryClick(cat)}
              >
                <span className="category-pill__label">{cat}</span>
              </button>
            ))}
          </div>

          {/* Advanced Filters Dropdown Panel */}
          {isDropdownOpen && (
            <div
              ref={dropdownRef}
              className="region-dropdown"
              style={{
                top: `${dropdownPosition.top}px`,
                left: `${dropdownPosition.left}px`,
              }}
            >
              {/* Categories Section */}
              <div className="region-dropdown__section">
                <div className="region-dropdown__header">
                  <h4>Filter by Categories</h4>
                  {dropdownCategories.length > 0 && (
                    <span>{dropdownCategories.length} selected</span>
                  )}
                </div>
                <div className="region-dropdown__search">
                  <input
                    type="text"
                    placeholder="Search categories…"
                    value={categorySearch}
                    onChange={(e) => setCategorySearch(e.target.value)}
                    className="region-dropdown__search-input"
                  />
                </div>
                <div className="region-dropdown__list region-dropdown__categories">
                  {filteredDropdownCategories.length > 0 ? (
                    filteredDropdownCategories.map((cat) => {
                      const isSelected = dropdownCategories.includes(cat);
                      return (
                        <button
                          key={cat}
                          type="button"
                          className={`region-option ${isSelected ? "region-option--selected" : ""}`}
                          onClick={() => toggleDropdownCategory(cat)}
                        >
                          {isSelected && (
                            <span className="region-option__check">✓</span>
                          )}
                          {cat}
                        </button>
                      );
                    })
                  ) : (
                    <p className="region-dropdown__no-results">No match</p>
                  )}
                </div>
              </div>

              <div className="region-dropdown__divider" />

              {/* Regions Section */}
              <div className="region-dropdown__section">
                <div className="region-dropdown__header">
                  <h4>Filter by Regions</h4>
                  {dropdownRegions.length > 0 && (
                    <span>{dropdownRegions.length} selected</span>
                  )}
                </div>
                <div className="region-dropdown__list">
                  {regions.map((regionCode) => {
                    const isSelected = dropdownRegions.includes(regionCode);
                    return (
                      <button
                        key={regionCode}
                        type="button"
                        className={`region-option ${isSelected ? "region-option--selected" : ""}`}
                        onClick={() => toggleDropdownRegion(regionCode)}
                      >
                        {isSelected && (
                          <span className="region-option__check">✓</span>
                        )}
                        {regionCode}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="region-dropdown__actions">
                <button
                  type="button"
                  className="region-dropdown__clear"
                  onClick={() => {
                    setDropdownCategories([]);
                    setDropdownRegions([]);
                  }}
                >
                  Clear All
                </button>
                <button
                  type="button"
                  className="region-dropdown__confirm"
                  onClick={applyDropdownFilters}
                >
                  Apply Filters
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {hasAnyAppliedFilter && (
        <div className="home__active-filter">
          Showing filters:
          {hasAppliedCategoryFilter
            ? ` Categories: ${appliedCategories.join(", ")}`
            : ""}
          {hasAppliedCategoryFilter && hasAppliedRegionFilter ? " |" : ""}
          {hasAppliedRegionFilter
            ? ` Regions: ${appliedRegions.join(", ")}`
            : ""}
        </div>
      )}

      {hasAnyAppliedFilter && (
        <div className="home__filter-actions">
          <button
            className="home__reset-feed-btn"
            onClick={loadPersonalizedFeed}
          >
            Back to Default Feed
          </button>
        </div>
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
            {hasAnyAppliedFilter
              ? `No videos found for selected filters`
              : "No videos found"}
          </h3>
          <p>
            {hasAnyAppliedFilter
              ? "Try changing your selected filters"
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
