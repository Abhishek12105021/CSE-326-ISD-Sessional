import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { MdDeleteOutline, MdHistory, MdOutlineSchedule } from "react-icons/md";
import { useAuth } from "../../context";
import { apiService } from "../../services";
import { API_ENDPOINTS } from "../../config";
import { formatDuration, formatTimeAgo } from "../../utils";
import "./WatchHistory.css";

const THUMBNAIL_QUALITIES = [
	"/maxresdefault.jpg",
	"/sddefault.jpg",
	"/hqdefault.jpg",
	"/mqdefault.jpg",
	"/default.jpg",
];

const getThumbnailByQuality = (thumbnailUrl, qualityIndex) => {
	if (!thumbnailUrl) return "";
	const baseUrl = thumbnailUrl.replace(
		/\/(default|mqdefault|hqdefault|sddefault|maxresdefault)\.jpg$/,
		""
	);
	return `${baseUrl}${THUMBNAIL_QUALITIES[qualityIndex]}`;
};

const HistoryThumbnail = ({ thumbnail, title }) => {
	const [qualityIndex, setQualityIndex] = useState(0);
	const [hasError, setHasError] = useState(false);

	const handleThumbnailError = () => {
		if (qualityIndex < THUMBNAIL_QUALITIES.length - 1) {
			setQualityIndex((prev) => prev + 1);
			return;
		}
		setHasError(true);
	};

	if (hasError) {
		return (
			<div className="watch-history__thumbnail-fallback" role="img" aria-label={title}>
				No Thumbnail
			</div>
		);
	}

	return (
		<img
			src={getThumbnailByQuality(thumbnail, qualityIndex)}
			alt={title}
			className="watch-history__thumbnail"
			loading="lazy"
			onError={handleThumbnailError}
		/>
	);
};

const WatchHistory = () => {
	const { isAuthenticated, session, loading: authLoading } = useAuth();
	const [historyItems, setHistoryItems] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [deletingIds, setDeletingIds] = useState([]);

	const authClient = useMemo(
		() => (session?.access_token ? apiService.withAuth(session.access_token) : null),
		[session?.access_token]
	);

	const loadHistory = useCallback(async () => {
		if (!authClient) {
			setHistoryItems([]);
			setLoading(false);
			return;
		}

		setLoading(true);
		setError("");

		try {
			const data = await authClient.get(API_ENDPOINTS.WATCH_HISTORY);
			setHistoryItems(Array.isArray(data?.watch_history) ? data.watch_history : []);
		} catch (err) {
			console.error("[WatchHistory] Failed to load history:", err);
			setError("We could not load your watch history right now.");
			setHistoryItems([]);
		} finally {
			setLoading(false);
		}
	}, [authClient]);

	useEffect(() => {
		if (authLoading) return;
		loadHistory();
	}, [authLoading, loadHistory]);

	const handleDelete = async (watchId) => {
		if (!authClient || !watchId) return;

		setDeletingIds((prev) => (prev.includes(watchId) ? prev : [...prev, watchId]));

		try {
			await authClient.delete(API_ENDPOINTS.WATCH_HISTORY, { watch_id: watchId });
			setHistoryItems((prev) => prev.filter((item) => item.watch_id !== watchId));
		} catch (err) {
			console.error("[WatchHistory] Failed to delete history item:", err);
			setError("Failed to remove a history item. Please try again.");
		} finally {
			setDeletingIds((prev) => prev.filter((id) => id !== watchId));
		}
	};

	if (authLoading) {
		return (
			<div className="watch-history watch-history--loading">
				<div className="loading-spinner" />
			</div>
		);
	}

	if (!isAuthenticated) {
		return (
			<div className="watch-history">
				<section className="watch-history__hero">
					<div className="watch-history__hero-icon">
						<MdHistory />
					</div>
					<h1 className="watch-history__title">Watch history</h1>
					<p className="watch-history__subtitle">
						Sign in to see the videos you have watched on this account.
					</p>
					<Link to="/signin" className="watch-history__cta">
						Sign in
					</Link>
				</section>
			</div>
		);
	}

	return (
		<div className="watch-history">
			<section className="watch-history__hero">
				<div className="watch-history__hero-icon">
					<MdHistory />
				</div>
				<div className="watch-history__hero-text">
					<h1 className="watch-history__title">Watch history</h1>
					<p className="watch-history__count">
						{historyItems.length} video{historyItems.length === 1 ? "" : "s"}
					</p>
				</div>
			</section>

			{loading ? (
				<div className="watch-history__state">
					<div className="loading-spinner" />
				</div>
			) : error ? (
				<div className="watch-history__state watch-history__state--error">
					<p>{error}</p>
					<button type="button" className="watch-history__retry" onClick={loadHistory}>
						Try again
					</button>
				</div>
			) : historyItems.length === 0 ? (
				<div className="watch-history__state watch-history__state--empty">
					<MdOutlineSchedule className="watch-history__empty-icon" />
					<h2>No history yet</h2>
					<p>Videos you watch will appear here automatically.</p>
					<Link to="/" className="watch-history__cta">
						Go to Home
					</Link>
				</div>
			) : (
				<div className="watch-history__list">
					{historyItems.map((item) => {
						const video = item.video;
						const watchId = item.watch_id;
						const isDeleting = deletingIds.includes(watchId);

						return (
							<article key={watchId} className="watch-history__item">
								<Link to={`/video/${video.id}`} className="watch-history__thumbnail-link">
									<div className="watch-history__thumbnail-wrap">
										<HistoryThumbnail thumbnail={video.thumbnail} title={video.title} />
										<span className="watch-history__duration">{video.duration}</span>
									</div>
								</Link>

								<div className="watch-history__content">
									<Link to={`/video/${video.id}`} className="watch-history__video-title">
										{video.title}
									</Link>

									<Link
										to={`/channel/${encodeURIComponent(video.channel.name)}`}
										className="watch-history__channel"
									>
										{video.channel.name}
									</Link>

									<div className="watch-history__meta">
										<span>{video.views}</span>
										<span>{video.timestamp}</span>
										<span>Watched for {formatDuration(item.watch_duration_seconds || 0)}</span>
									</div>

									<div className="watch-history__time-row">
										<MdOutlineSchedule />
										<span>
											{item.started_at_local || formatTimeAgo(item.started_at)}
										</span>
									</div>
								</div>

								<button
									type="button"
									className="watch-history__delete"
									onClick={() => handleDelete(watchId)}
									disabled={isDeleting}
									title="Remove from history"
								>
									<MdDeleteOutline />
								</button>
							</article>
						);
					})}
				</div>
			)}
		</div>
	);
};

export default WatchHistory;
