import React from "react";
import { useSearchParams, Link } from "react-router-dom";
import { MdVerified, MdOutlineTune } from "react-icons/md";
import { videos } from "../../data/sampleData";
import "./Search.css";

const Search = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") || "";

  const filteredVideos = videos.filter(
    (v) =>
      v.title.toLowerCase().includes(query.toLowerCase()) ||
      v.channel.name.toLowerCase().includes(query.toLowerCase()) ||
      v.category.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="search-page">
      <div className="search-page__header">
        <button className="search-page__filter-btn">
          <MdOutlineTune /> Filters
        </button>
      </div>

      {filteredVideos.length > 0 ? (
        filteredVideos.map((video) => (
          <div key={video.id} className="search-result-card">
            <Link to={`/video/${video.id}`}>
              <div className="search-result-card__thumbnail-container">
                <img
                  className="search-result-card__thumbnail"
                  src={video.thumbnail}
                  alt={video.title}
                  loading="lazy"
                />
                <span className="search-result-card__duration">
                  {video.duration}
                </span>
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
                to={`/channel/${video.channel.id}`}
                className="search-result-card__channel"
                style={{ textDecoration: "none" }}
              >
                <img
                  className="search-result-card__channel-avatar"
                  src={video.channel.avatar}
                  alt={video.channel.name}
                />
                <span className="search-result-card__channel-name">
                  {video.channel.name}
                  {video.channel.verified && (
                    <MdVerified style={{ fontSize: 14 }} />
                  )}
                </span>
              </Link>
              <p className="search-result-card__description">
                {video.description}
              </p>
            </div>
          </div>
        ))
      ) : (
        <div className="search-page__no-results">
          <h3>No results found for "{query}"</h3>
          <p>Try different keywords or check the spelling</p>
        </div>
      )}
    </div>
  );
};

export default Search;
