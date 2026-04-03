import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { MdVerified, MdOutlineTune } from "react-icons/md";
import { apiService } from "../../services";
import { API_ENDPOINTS } from "../../config";
import "./Search.css";

const Search = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") || "";

  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const shownIds = useRef([]);

  // Fetch on query change
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    setLoading(true);
    shownIds.current = [];

    apiService.post(`${API_ENDPOINTS.SEARCH}?q=${encodeURIComponent(query)}&limit=25`)
      .then(data => {
        const videos = data?.videos || [];
        shownIds.current = videos.map(v => v.id);
        setResults(videos);
        setHasMore(videos.length >= 25);
      })
      .catch(err => console.error("[Search] Failed:", err))
      .finally(() => setLoading(false));
  }, [query]);

  // Load more results
  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore || !query.trim()) return;
    setLoadingMore(true);
    try {
      const data = await apiService.post(API_ENDPOINTS.SEARCH_RELOAD, {
        q: query,
        excluded_video_ids: shownIds.current,
        limit: 25,
      });
      const videos = data?.videos || [];
      shownIds.current = [...shownIds.current, ...videos.map(v => v.id)];
      setResults(prev => [...prev, ...videos]);
      setHasMore(videos.length >= 25);
    } catch (err) {
      console.error("[Search] Load more failed:", err);
    } finally {
      setLoadingMore(false);
    }
  }, [query, loadingMore, hasMore]);

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
        <button className="search-page__filter-btn">
          <MdOutlineTune /> Filters
        </button>
      </div>

      {results.length > 0 ? (
        <>
          {results.map((video) => (
            <div key={video.id} className="search-result-card">
              <Link to={`/video/${video.id}`}>
                <div className="search-result-card__thumbnail-container">
                  <img
                    className="search-result-card__thumbnail"
                    src={video.thumbnail}
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
                  to={`/channel/${video.channel?.id}`}
                  className="search-result-card__channel"
                  style={{ textDecoration: "none" }}
                >
                  <img
                    className="search-result-card__channel-avatar"
                    src={video.channel?.avatar}
                    alt={video.channel?.name}
                  />
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
      ) : query.trim() ? (
        <div className="search-page__no-results">
          <h3>No results found for &quot;{query}&quot;</h3>
          <p>Try different keywords or check the spelling</p>
        </div>
      ) : null}
    </div>
  );
};

export default Search;
