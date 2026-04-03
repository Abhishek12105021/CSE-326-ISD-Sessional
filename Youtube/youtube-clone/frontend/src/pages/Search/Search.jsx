import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { MdVerified, MdOutlineTune } from "react-icons/md";
import { useAuth } from "../../context";
import { apiService } from "../../services";
import { API_ENDPOINTS } from "../../config";
import "./Search.css";

const LIMIT = 25;
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

const Search = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") || "";
  const { isAuthenticated, session } = useAuth();

  const [results, setResults] = useState([]);
  const [channels, setChannels] = useState([]);
  const [subscribedChannelNames, setSubscribedChannelNames] = useState([]);
  const [subscriptionBusyNames, setSubscriptionBusyNames] = useState([]);
  const [subscriptionSuccessNames, setSubscriptionSuccessNames] = useState([]);
  const [categories, setCategories] = useState(["All"]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [showAllChannels, setShowAllChannels] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 });
  const [categorySearch, setCategorySearch] = useState("");
  const [dropdownCategories, setDropdownCategories] = useState([]);
  const [dropdownRegions, setDropdownRegions] = useState([]);
  const [appliedCategories, setAppliedCategories] = useState([]);
  const [appliedRegions, setAppliedRegions] = useState([]);

  const dropdownTriggerRef = useRef(null);
  const dropdownRef = useRef(null);
  const shownIds = useRef([]);

  const dbCategories = useMemo(
    () => categories.filter((cat) => cat !== "All"),
    [categories]
  );
  const filteredDropdownCategories = useMemo(
    () =>
      categorySearch
        ? dbCategories.filter((cat) =>
            cat.toLowerCase().includes(categorySearch.toLowerCase())
          )
        : dbCategories,
    [dbCategories, categorySearch]
  );
  const hasAnyAppliedFilter =
    appliedCategories.length > 0 || appliedRegions.length > 0;
  const totalAppliedCount = appliedCategories.length + appliedRegions.length;
  const visibleChannels = showAllChannels ? channels : channels.slice(0, 3);
  const hasHiddenChannels = channels.length > 3;
  const isChannelSubscribed = useCallback(
    (channelName) => subscribedChannelNames.includes(channelName),
    [subscribedChannelNames]
  );

  const loadSubscribedChannels = useCallback(async () => {
    if (!isAuthenticated || !session?.access_token) {
      setSubscribedChannelNames([]);
      return;
    }

    try {
      const subscriptionData = await apiService
        .withAuth(session.access_token)
        .get(API_ENDPOINTS.SUBSCRIPTIONS);
      setSubscribedChannelNames(subscriptionData?.channels || []);
    } catch (error) {
      console.error("[Search] Failed to load subscriptions:", error);
      setSubscribedChannelNames([]);
    }
  }, [isAuthenticated, session?.access_token]);

  useEffect(() => {
    loadSubscribedChannels();
  }, [loadSubscribedChannels]);

  const toggleChannelSubscription = useCallback(
    async (channelName) => {
      if (!isAuthenticated || !session?.access_token || !channelName) return;

      setSubscriptionBusyNames((prev) =>
        prev.includes(channelName) ? prev : [...prev, channelName]
      );

      try {
        const client = apiService.withAuth(session.access_token);
        const currentlySubscribed = isChannelSubscribed(channelName);

        if (currentlySubscribed) {
          await client.delete(API_ENDPOINTS.SUBSCRIBE, { channel_name: channelName });
          setSubscribedChannelNames((prev) => prev.filter((name) => name !== channelName));
        } else {
          await client.post(API_ENDPOINTS.SUBSCRIBE, { channel_name: channelName });
          setSubscribedChannelNames((prev) => [...prev, channelName]);
        }

        setSubscriptionSuccessNames((prev) =>
          prev.includes(channelName) ? prev : [...prev, channelName]
        );
        window.dispatchEvent(new Event("yt:subscriptions-updated"));
        setTimeout(() => {
          setSubscriptionSuccessNames((prev) =>
            prev.filter((name) => name !== channelName)
          );
        }, 850);
      } catch (error) {
        console.error("[Search] Channel subscription toggle failed:", error);
      } finally {
        setSubscriptionBusyNames((prev) => prev.filter((name) => name !== channelName));
      }
    },
    [isAuthenticated, session?.access_token, isChannelSubscribed]
  );

  const getHqThumbnail = (thumbnailUrl) => {
    if (!thumbnailUrl) return "";
    return thumbnailUrl.replace(
      /\/(default|mqdefault|hqdefault|sddefault|maxresdefault)\.jpg$/,
      "/hqdefault.jpg"
    );
  };

  const generateColorHash = (value) => {
    const str = value || "Channel";
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const colors = [
      ["#FF6B6B", "#FFE66D"],
      ["#4ECDC4", "#44A08D"],
      ["#95E1D3", "#38A169"],
      ["#FA8072", "#FFB347"],
      ["#87CEEB", "#4169E1"],
      ["#DDA0DD", "#BA55D3"],
      ["#20B2AA", "#00CED1"],
      ["#FF69B4", "#FF1493"],
    ];
    return colors[Math.abs(hash) % colors.length];
  };

  const getInitials = (name) => {
    const normalized = (name || "C").trim();
    if (!normalized) return "C";
    return normalized
      .split(" ")
      .filter(Boolean)
      .map((part) => part[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const getAvatarGradient = (name) => {
    const [start, end] = generateColorHash(name);
    return `linear-gradient(135deg, ${start} 0%, ${end} 100%)`;
  };

  const matchesQuery = useCallback(
    (video) => {
      if (!query.trim()) return true;
      const q = query.trim().toLowerCase();
      const title = (video?.title || "").toLowerCase();
      const channelName = (video?.channel?.name || "").toLowerCase();
      return title.includes(q) || channelName.includes(q);
    },
    [query]
  );

  const fetchSearchResults = useCallback(
    async (append = false) => {
      if (!query.trim()) {
        setResults([]);
        setChannels([]);
        setHasMore(false);
        setShowAllChannels(false);
        return;
      }

      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        shownIds.current = [];
      }

      try {
        const excludedIds = append ? shownIds.current : [];

        let data;
        let channelData = null;

        if (append) {
          data = hasAnyAppliedFilter
            ? await apiService.post(API_ENDPOINTS.FILTER_HOMEFEED_RELOAD, {
                categories: appliedCategories,
                regions: appliedRegions,
                excluded_video_ids: excludedIds,
                limit: LIMIT,
              })
            : await apiService.post(API_ENDPOINTS.SEARCH_RELOAD, {
                q: query,
                excluded_video_ids: excludedIds,
                limit: LIMIT,
              });
        } else {
          const videoRequest = hasAnyAppliedFilter
            ? apiService.post(API_ENDPOINTS.FILTER_HOMEFEED, {
                categories: appliedCategories,
                regions: appliedRegions,
                excluded_video_ids: excludedIds,
                limit: LIMIT,
              })
            : apiService.post(
                `${API_ENDPOINTS.SEARCH}?q=${encodeURIComponent(query)}&limit=${LIMIT}`
              );

          const [videoResult, channelResult] = await Promise.allSettled([
            videoRequest,
            apiService.post(API_ENDPOINTS.SEARCH_CHANNELS, {
              q: query,
              limit: 100,
            }),
          ]);

          data = videoResult.status === "fulfilled" ? videoResult.value : null;
          channelData =
            channelResult.status === "fulfilled" ? channelResult.value : null;
        }

        const sourceVideos = data?.videos || [];
        shownIds.current = [
          ...shownIds.current,
          ...sourceVideos.map((v) => v.id),
        ];

        const videos = hasAnyAppliedFilter
          ? sourceVideos.filter(matchesQuery)
          : sourceVideos;

        if (append) {
          setResults((prev) => [...prev, ...videos]);
        } else {
          setResults(videos);
          setChannels(channelData?.channels || []);
          setShowAllChannels(false);
        }

        if (hasAnyAppliedFilter && typeof data?.has_more === "boolean") {
          setHasMore(data.has_more);
        } else {
          setHasMore(sourceVideos.length >= LIMIT);
        }
      } catch (err) {
        console.error("[Search] Failed:", err);
        if (!append) {
          setResults([]);
          setChannels([]);
          setHasMore(false);
          setShowAllChannels(false);
        }
      } finally {
        if (append) {
          setLoadingMore(false);
        } else {
          setLoading(false);
        }
      }
    },
    [query, hasAnyAppliedFilter, appliedCategories, appliedRegions, matchesQuery]
  );

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

  const applyDropdownFilters = useCallback(() => {
    setAppliedCategories([...dropdownCategories]);
    setAppliedRegions([...dropdownRegions]);
    setIsDropdownOpen(false);
  }, [dropdownCategories, dropdownRegions]);

  const resetFilters = useCallback(() => {
    setDropdownCategories([]);
    setDropdownRegions([]);
    setAppliedCategories([]);
    setAppliedRegions([]);
    setIsDropdownOpen(false);
  }, []);

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
    [dbCategories]
  );

  const toggleDropdownRegion = useCallback((regionCode) => {
    setDropdownRegions((prev) =>
      prev.includes(regionCode)
        ? prev.filter((r) => r !== regionCode)
        : [...prev, regionCode]
    );
  }, []);

  // Categories for dropdown
  useEffect(() => {
    apiService
      .get(API_ENDPOINTS.CATEGORIES)
      .then((data) => {
        const incoming = data?.categories || [];
        const uniqueDbCategories = Array.from(
          new Set(incoming.filter((cat) => cat && cat !== "All"))
        );
        setCategories(["All", ...uniqueDbCategories]);
      })
      .catch(() => {});
  }, []);

  // Fetch on query change
  useEffect(() => {
    fetchSearchResults(false);
  }, [query, appliedCategories, appliedRegions, fetchSearchResults]);

  useEffect(() => {
    if (!isDropdownOpen) return;

    setDropdownCategories([...appliedCategories]);
    setDropdownRegions([...appliedRegions]);
    setCategorySearch("");
    updateDropdownPosition();

    const handleViewportChange = () => updateDropdownPosition();
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);

    return () => {
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [
    isDropdownOpen,
    appliedCategories,
    appliedRegions,
    updateDropdownPosition,
  ]);

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

  // Load more results
  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore || !query.trim()) return;
    await fetchSearchResults(true);
  }, [query, loadingMore, hasMore, fetchSearchResults]);

  // Scroll listener
  useEffect(() => {
    const handleScroll = () => {
      const nearBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 600;
      if (nearBottom) loadMore();
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [loadMore]);

  if (loading) {
    return (
      <div className="search-page" style={{ textAlign: "center", padding: "80px" }}>
        <div className="loading-spinner" />
        <p style={{ marginTop: "16px", color: "#606060" }}>Searching…</p>
      </div>
    );
  }

  return (
    <div className="search-page">
      <div className="search-page__header">
        <button
          ref={dropdownTriggerRef}
          className={`search-page__filter-btn ${isDropdownOpen ? "search-page__filter-btn--open" : ""}`}
          onClick={() => setIsDropdownOpen((prev) => !prev)}
        >
          <MdOutlineTune /> Filters
          {hasAnyAppliedFilter && (
            <span className="search-page__filter-badge">{totalAppliedCount}</span>
          )}
        </button>
      </div>

      {channels.length > 0 && (
        <section className="search-channels-section">
          <div className="search-channels-section__header">
            <div>
              <h3 className="search-channels-title">Channels</h3>
              <p className="search-channels-subtitle">
                {channels.length} channel{channels.length === 1 ? "" : "s"} found
              </p>
            </div>
          </div>

          <div className="search-channels-grid">
            {visibleChannels.map((channel) => (
              <article key={channel.id} className="search-channel-card">
                <Link
                  to={`/channel/${encodeURIComponent(channel.id)}`}
                  className="search-channel-card__main"
                >
                  <div className="search-channel-card__avatar-wrap">
                    <img
                      src={channel.avatar}
                      alt={channel.name}
                      className="search-channel-card__avatar"
                    />
                  </div>
                  <div className="search-channel-card__body">
                    <div className="search-channel-card__title-row">
                      <h4 className="search-channel-card__name">{channel.name}</h4>
                      {channel.verified && (
                        <span className="search-channel-card__verified" aria-label="Verified channel">
                          <MdVerified />
                        </span>
                      )}
                    </div>
                    <p className="search-channel-card__description">
                      {channel.description}
                    </p>
                    <p className="search-channel-card__meta">
                      <span className="search-channel-card__handle">
                        {channel.handle || `@${channel.id.toLowerCase().replace(/\s+/g, "")}`}
                      </span>
                      <span className="search-channel-card__dot">•</span>
                      <span>
                        {channel.video_count} video{channel.video_count === 1 ? "" : "s"}
                      </span>
                    </p>
                  </div>
                </Link>
                {isAuthenticated && (
                  <button
                    type="button"
                    className={`search-channel-card__subscribe-btn ${isChannelSubscribed(channel.id) ? "search-channel-card__subscribe-btn--subscribed" : ""} ${subscriptionBusyNames.includes(channel.id) ? "search-channel-card__subscribe-btn--loading" : ""} ${subscriptionSuccessNames.includes(channel.id) ? "search-channel-card__subscribe-btn--success" : ""}`}
                    onClick={() => toggleChannelSubscription(channel.id)}
                    disabled={subscriptionBusyNames.includes(channel.id)}
                  >
                    <span className="search-channel-card__subscribe-label">
                      {isChannelSubscribed(channel.id) ? "Subscribed" : "Subscribe"}
                    </span>
                  </button>
                )}
              </article>
            ))}
          </div>

          {hasHiddenChannels && (
            <div className="search-channels-expand">
              <button
                type="button"
                className="search-channels-expand__button"
                onClick={() => setShowAllChannels((prev) => !prev)}
                aria-expanded={showAllChannels}
              >
                {showAllChannels ? "Show less" : "Show more"}
                <span className={`search-channels-expand__chevron ${showAllChannels ? "search-channels-expand__chevron--up" : ""}`}>
                  ˅
                </span>
              </button>
            </div>
          )}
        </section>
      )}

      {isDropdownOpen && (
        <div
          ref={dropdownRef}
          className="search-filter-dropdown"
          style={{
            top: `${dropdownPosition.top}px`,
            left: `${dropdownPosition.left}px`,
          }}
        >
          <div className="search-filter-dropdown__section">
            <div className="search-filter-dropdown__header">
              <h4>Filter by Categories</h4>
              {dropdownCategories.length > 0 && (
                <span>{dropdownCategories.length} selected</span>
              )}
            </div>

            <div className="search-filter-dropdown__search">
              <input
                type="text"
                placeholder="Search categories..."
                value={categorySearch}
                onChange={(e) => setCategorySearch(e.target.value)}
                className="search-filter-dropdown__search-input"
              />
            </div>

            <div className="search-filter-dropdown__list search-filter-dropdown__categories">
              <button
                type="button"
                className={`search-filter-option ${
                  dropdownCategories.length === dbCategories.length &&
                  dbCategories.length > 0
                    ? "search-filter-option--selected"
                    : ""
                }`}
                onClick={() => toggleDropdownCategory("All")}
              >
                All
              </button>

              {filteredDropdownCategories.length > 0 ? (
                filteredDropdownCategories.map((cat) => {
                  const isSelected = dropdownCategories.includes(cat);
                  return (
                    <button
                      key={cat}
                      type="button"
                      className={`search-filter-option ${
                        isSelected ? "search-filter-option--selected" : ""
                      }`}
                      onClick={() => toggleDropdownCategory(cat)}
                    >
                      {isSelected && (
                        <span className="search-filter-option__check">✓</span>
                      )}
                      {cat}
                    </button>
                  );
                })
              ) : (
                <p className="search-filter-dropdown__no-results">No match</p>
              )}
            </div>
          </div>

          <div className="search-filter-dropdown__divider" />

          <div className="search-filter-dropdown__section">
            <div className="search-filter-dropdown__header">
              <h4>Filter by Regions</h4>
              {dropdownRegions.length > 0 && (
                <span>{dropdownRegions.length} selected</span>
              )}
            </div>
            <div className="search-filter-dropdown__list">
              {HARDCODED_REGIONS.map((regionCode) => {
                const isSelected = dropdownRegions.includes(regionCode);
                return (
                  <button
                    key={regionCode}
                    type="button"
                    className={`search-filter-option ${
                      isSelected ? "search-filter-option--selected" : ""
                    }`}
                    onClick={() => toggleDropdownRegion(regionCode)}
                  >
                    {isSelected && (
                      <span className="search-filter-option__check">✓</span>
                    )}
                    {regionCode}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="search-filter-dropdown__actions">
            <button
              type="button"
              className="search-filter-dropdown__clear"
              onClick={() => {
                setDropdownCategories([]);
                setDropdownRegions([]);
              }}
            >
              Clear All
            </button>
            <button
              type="button"
              className="search-filter-dropdown__confirm"
              onClick={applyDropdownFilters}
            >
              Apply Filters
            </button>
          </div>
        </div>
      )}

      {hasAnyAppliedFilter && (
        <div className="search-page__active-filter">
          Showing filters:
          {appliedCategories.length > 0
            ? ` Categories: ${appliedCategories.join(", ")}`
            : ""}
          {appliedCategories.length > 0 && appliedRegions.length > 0 ? " |" : ""}
          {appliedRegions.length > 0 ? ` Regions: ${appliedRegions.join(", ")}` : ""}
        </div>
      )}

      {hasAnyAppliedFilter && (
        <div className="search-page__filter-actions">
          <button className="search-page__reset-btn" onClick={resetFilters}>
            Back to Search Results
          </button>
        </div>
      )}

      {channels.length > 0 && <div className="search-results-divider" />}

      {query.trim() && results.length === 0 && channels.length > 0 && (
        <div className="search-page__empty-videos">
          <h3>No videos matched your search</h3>
          <p>
            Channel matches are shown above. Try a broader query if you want video results.
          </p>
        </div>
      )}

      {results.length > 0 ? (
        <>
          {results.map((video) => (
            <div key={video.id} className="search-result-card">
              <Link to={`/video/${video.id}`}>
                <div className="search-result-card__thumbnail-container">
                  <img
                    className="search-result-card__thumbnail"
                    src={getHqThumbnail(video.thumbnail)}
                    alt={video.title}
                    loading="lazy"
                  />
                  <span className="search-result-card__duration">{video.duration}</span>
                </div>
              </Link>
              <div className="search-result-card__info">
                <Link to={`/video/${video.id}`} style={{ textDecoration: "none" }}>
                  <h3 className="search-result-card__title">{video.title}</h3>
                </Link>
                <div className="search-result-card__meta">
                  <span>{video.views}</span>
                  <span>{video.timestamp}</span>
                </div>
                <Link
                  to={`/channel/${encodeURIComponent(video.channel?.name || "")}`}
                  className="search-result-card__channel"
                  style={{ textDecoration: "none" }}
                >
                  <div
                    className="search-result-card__channel-avatar-fallback"
                    style={{
                      background: getAvatarGradient(video.channel?.name),
                    }}
                    aria-label={video.channel?.name}
                  >
                    <span className="search-result-card__channel-avatar-initials">
                      {getInitials(video.channel?.name)}
                    </span>
                  </div>
                  <span className="search-result-card__channel-name">
                    {video.channel?.name}
                    {video.channel?.verified && <MdVerified style={{ fontSize: 14 }} />}
                  </span>
                </Link>
              </div>
            </div>
          ))}
          {loadingMore && (
            <div style={{ textAlign: "center", padding: "24px" }}>
              <div className="loading-spinner" />
            </div>
          )}
          {!hasMore && (
            <div style={{ textAlign: "center", padding: "24px", color: "#606060" }}>
              <p>No more results</p>
            </div>
          )}
        </>
      ) : query.trim() && channels.length === 0 ? (
        <div className="search-page__no-results">
          <h3>{hasAnyAppliedFilter ? "No videos" : `No results found for "${query}"`}</h3>
          <p>
            {hasAnyAppliedFilter
              ? "No videos available for the selected filters"
              : "Try different keywords or check the spelling"}
          </p>
        </div>
      ) : null}
    </div>
  );
};

export default Search;
