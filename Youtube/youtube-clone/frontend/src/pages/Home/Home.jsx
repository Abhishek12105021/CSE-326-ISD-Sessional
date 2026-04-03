import { useState, useEffect, useCallback, useRef } from "react";
import { VideoCard } from "../../components";
import { AiOutlineDown } from "react-icons/ai";
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

const areSameSelections = (a, b) =>
  a.length === b.length && a.every((item) => b.includes(item));

const Home = () => {
  const { isAuthenticated, session, guestId, region, getWatchedVideoIds } =
    useAuth();

  const [videos, setVideos] = useState([]);
  const [categories, setCategories] = useState(["All"]);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [appliedCategories, setAppliedCategories] = useState([]);
  const [regions, setRegions] = useState([]);
  const [selectedRegions, setSelectedRegions] = useState([]);
  const [appliedRegions, setAppliedRegions] = useState([]);
  const [isRegionDropdownOpen, setIsRegionDropdownOpen] = useState(false);
  const [regionDropdownPosition, setRegionDropdownPosition] = useState({
    top: 0,
    left: 0,
  });
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const shownIds = useRef(new Set());
  const regionTriggerRef = useRef(null);
  const regionDropdownRef = useRef(null);
  const LIMIT = 30;

  const dbCategories = categories.filter((cat) => cat !== "All");
  const allCategoriesSelected =
    dbCategories.length > 0 &&
    selectedCategories.length === dbCategories.length &&
    dbCategories.every((cat) => selectedCategories.includes(cat));
  const hasAppliedCategoryFilter = appliedCategories.length > 0;
  const hasAppliedRegionFilter = appliedRegions.length > 0;
  const hasAnyAppliedFilter =
    hasAppliedCategoryFilter || hasAppliedRegionFilter;
  const hasPendingFilterChanges =
    !areSameSelections(selectedCategories, appliedCategories) ||
    !areSameSelections(selectedRegions, appliedRegions);

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

  // Fetch regions once on mount (frontend hardcoded source)
  useEffect(() => {
    const fetchRegions = async () => {
      setRegions(HARDCODED_REGIONS);
    };
    fetchRegions();
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
      setAppliedRegions([]);
      setSelectedRegions([]);
    } catch (err) {
      console.error("[Home] Failed to fetch feed:", err);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, session, guestId, region, getWatchedVideoIds, LIMIT]);

  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  const updateRegionDropdownPosition = useCallback(() => {
    const trigger = regionTriggerRef.current;
    if (!trigger) return;

    const rect = trigger.getBoundingClientRect();
    const estimatedWidth = 420;
    const viewportPadding = 12;
    const maxLeft = window.innerWidth - estimatedWidth - viewportPadding;
    const safeLeft = Math.max(viewportPadding, Math.min(rect.left, maxLeft));

    setRegionDropdownPosition({
      top: rect.bottom + 10,
      left: safeLeft,
    });
  }, []);

  useEffect(() => {
    if (!isRegionDropdownOpen) return;

    updateRegionDropdownPosition();

    const handleViewportChange = () => updateRegionDropdownPosition();
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);

    return () => {
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [isRegionDropdownOpen, updateRegionDropdownPosition]);

  useEffect(() => {
    if (!isRegionDropdownOpen) return;

    const handleOutsideClick = (event) => {
      const target = event.target;
      if (
        regionDropdownRef.current?.contains(target) ||
        regionTriggerRef.current?.contains(target)
      ) {
        return;
      }
      setIsRegionDropdownOpen(false);
    };

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [isRegionDropdownOpen]);

  const toggleCategorySelection = useCallback(
    (category) => {
      setSelectedCategories((prev) => {
        if (category === "All") {
          const isAllSelected =
            dbCategories.length > 0 &&
            prev.length === dbCategories.length &&
            dbCategories.every((cat) => prev.includes(cat));
          return isAllSelected ? [] : dbCategories;
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

  const toggleRegionSelection = useCallback((regionCode) => {
    setSelectedRegions((prev) => {
      if (prev.includes(regionCode)) {
        return prev.filter((r) => r !== regionCode);
      }
      return [...prev, regionCode];
    });
  }, []);

  const applyFilters = useCallback(async () => {
    const normalizedCategories = [...selectedCategories];
    const normalizedRegions = [...selectedRegions];

    if (normalizedCategories.length === 0 && normalizedRegions.length === 0) {
      setIsRegionDropdownOpen(false);
      await fetchFeed();
      return;
    }

    setLoading(true);
    shownIds.current = new Set();

    try {
      const data = await apiService.post(API_ENDPOINTS.FILTER_HOMEFEED, {
        categories: normalizedCategories,
        regions: normalizedRegions,
        excluded_video_ids: [],
        limit: LIMIT,
      });

      const fetched = data?.videos || [];
      fetched.forEach((v) => shownIds.current.add(v.id));

      setVideos(fetched);
      setAppliedCategories(normalizedCategories);
      setSelectedCategories(normalizedCategories);
      setAppliedRegions(normalizedRegions);
      setSelectedRegions(normalizedRegions);
      setIsRegionDropdownOpen(false);
      setHasMore(fetched.length > 0);
    } catch (err) {
      console.error("[Home] Failed to apply unified filters:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedCategories, selectedRegions, fetchFeed, LIMIT]);

  const loadPersonalizedFeed = useCallback(async () => {
    setIsRegionDropdownOpen(false);
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
        <>
          <div className="category-bar">
            <button
              ref={regionTriggerRef}
              className={`category-pill region-dropdown-trigger ${isRegionDropdownOpen ? "region-dropdown-trigger--open" : ""}`}
              onClick={() => setIsRegionDropdownOpen((prev) => !prev)}
            >
              <span>Regions ({selectedRegions.length})</span>
              <AiOutlineDown className="region-dropdown-trigger__icon" />
            </button>

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

            {hasPendingFilterChanges && (
              <button
                className="category-pill category-pill--active category-pill--confirm"
                onClick={applyFilters}
              >
                Apply Filters
              </button>
            )}
          </div>

          {isRegionDropdownOpen && (
            <div
              ref={regionDropdownRef}
              className="region-dropdown"
              style={{
                top: `${regionDropdownPosition.top}px`,
                left: `${regionDropdownPosition.left}px`,
              }}
            >
              <div className="region-dropdown__header">
                <h4>Filter By Region</h4>
                <span>{selectedRegions.length} selected</span>
              </div>

              <div className="region-dropdown__list">
                {regions.map((regionCode) => (
                  <button
                    key={regionCode}
                    type="button"
                    className={`region-option ${selectedRegions.includes(regionCode) ? "region-option--selected" : ""}`}
                    onClick={() => toggleRegionSelection(regionCode)}
                  >
                    {regionCode}
                  </button>
                ))}
              </div>

              <div className="region-dropdown__actions">
                <button
                  type="button"
                  className="region-dropdown__clear"
                  onClick={() => setSelectedRegions([])}
                >
                  Clear
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
          <p>You&apos;ve reached the end</p>
        </div>
      )}
    </div>
  );
};

export default Home;
