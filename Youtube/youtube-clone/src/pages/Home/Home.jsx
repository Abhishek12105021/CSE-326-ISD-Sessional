import React, { useState } from "react";
import VideoCard from "../../components/VideoCard/VideoCard";
import { videos, categories, shortsData } from "../../data/sampleData";
import { SiYoutubeshorts } from "react-icons/si";
import features from "../../features.config";
import "./Home.css";

const Home = () => {
  const [activeCategory, setActiveCategory] = useState("All");

  const filteredVideos =
    activeCategory === "All"
      ? videos
      : videos.filter((v) => v.category === activeCategory);

  const showShorts = features.shorts && features.shortsSection && activeCategory === "All";

  return (
    <div className="home">
      {/* Category Pills — toggle via features.categoryChips */}
      {features.categoryChips && (
        <div className="category-bar">
          {categories.map((cat) => (
            <button
              key={cat}
              className={`category-pill ${
                activeCategory === cat ? "category-pill--active" : ""
              }`}
              onClick={() => setActiveCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* Shorts Section — toggle via features.shorts + features.shortsSection */}
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

      {filteredVideos.length === 0 && (
        <div style={{ textAlign: "center", padding: "48px", color: "#606060" }}>
          <h3>No videos found for "{activeCategory}"</h3>
          <p>Try selecting a different category</p>
        </div>
      )}
    </div>
  );
};

export default Home;
