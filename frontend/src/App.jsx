import { useEffect, useState } from "react";
import "./App.css";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "/api";
const rankingLabels = {
  tfidf_similarity: "Keyword similarity",
  title_relevance: "Title relevance",
  content_relevance: "Content relevance",
  url_relevance: "URL relevance",
  exact_phrase: "Exact phrase",
  source_quality: "Source quality",
  freshness: "Freshness",
};

function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const [totalResults, setTotalResults] = useState(0);
  const [stats, setStats] = useState(null);
  const [expandedResult, setExpandedResult] = useState(null);

  useEffect(() => {
    fetch(`${apiBaseUrl}/stats`)
      .then((response) => (response.ok ? response.json() : null))
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  const handleSearch = async (searchText = query) => {
    const text = searchText.trim();

    if (!text) return;

    setQuery(text);
    setLoading(true);
    setSearched(true);
    setError("");
    setExpandedResult(null);

    try {
      const response = await fetch(
        `${apiBaseUrl}/search?query=${encodeURIComponent(text)}`
      );

      if (!response.ok) {
        throw new Error("Search request failed");
      }

      const data = await response.json();
      setResults(data.results || []);
      setTotalResults(data.total_results || 0);
    } catch (error) {
      console.error("Search Error:", error);
      setResults([]);
      setTotalResults(0);
      setError("YEXA could not reach the search service. Start the backend and try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter") {
      handleSearch();
    }
  };

  return (
    <div className="yexa-app">

      <nav className="navbar">
        <div className="brand" onClick={() => window.location.reload()}>
          <span className="brand-icon">Y</span>
          <span className="brand-name">YEXA</span>
        </div>

        <div className="nav-links">
          <span>About</span>
          <span>Privacy</span>
        </div>
      </nav>

      <main className={searched ? "main results-mode" : "main"}>

        {!searched && (
          <section className="hero">
            <div className="logo-large">
              <span>Y</span>EXA
            </div>

            <p className="tagline">
              Search your own web, simply.
            </p>

            {stats && (
              <p className="index-status">
                {stats.documents} indexed documents · {stats.terms} searchable terms
              </p>
            )}
          </section>
        )}

        <section className="search-section">

          <div className="search-box">
            <span className="search-icon">⌕</span>

            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search anything..."
            />

                  {query && (
              <button
                className="clear-btn"
                onClick={() => {
                  setQuery("");
                  setResults([]);
                  setSearched(false);
                  setError("");
                }}
              >
                ×
              </button>
            )}

            <button
              className="search-btn"
              onClick={() => handleSearch()}
            >
              Search
            </button>
          </div>

          {!searched && (
            <div className="quick-searches">
              <span>Try:</span>

              <button onClick={() => handleSearch("flutter")}>
                Flutter
              </button>

              <button onClick={() => handleSearch("python")}>
                Python
              </button>

              <button onClick={() => handleSearch("artificial intelligence")}>
                AI
              </button>
            </div>
          )}

        </section>

        {searched && (
          <section className="results-container">

            <div className="results-header">
                <span>
                Search results for <strong>"{query}"</strong>
              </span>

              {!loading && (
                <span className="result-count">
                  {totalResults} result{totalResults !== 1 ? "s" : ""}
                </span>
              )}
            </div>

            {loading && (
              <div className="loading">
                <div className="loader"></div>
                <p>YEXA is searching...</p>
              </div>
            )}

            {!loading && error && (
              <div className="search-error" role="alert">{error}</div>
            )}

            {!loading && !error && results.length === 0 && (
              <div className="no-results">
                <div className="no-results-icon">⌕</div>
                <h2>No results found</h2>
                <p>
                  Try different keywords or a simpler search.
                </p>
              </div>
            )}

            {!loading &&
              results.map((result) => (
                <article className="result-card" key={result.id}>

                  <a
                    href={result.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="result-title"
                  >
                    {result.title}
                  </a>

                  <div className="result-url">
                    {result.url}
                  </div>

                  <p className="result-description">
                    {result.description}
                  </p>

                  <div className="result-meta">
                    <span>
                      Relevance: <strong>{result.score}</strong>
                    </span>

                    {result.similarity !== undefined && (
                      <span>
                        Similarity:{" "}
                        <strong>{result.similarity}</strong>
                      </span>
                    )}

                    <span>
                      Quality: <strong>{result.source_quality}/100</strong>
                    </span>
                  </div>

                  <button
                    className="why-result"
                    onClick={() => setExpandedResult(
                      expandedResult === result.id ? null : result.id
                    )}
                  >
                    {expandedResult === result.id ? "Hide ranking details" : "Why this result?"}
                  </button>

                  {expandedResult === result.id && (
                    <div className="ranking-details">
                      <p>{result.match_summary}</p>
                      <ul>
                        {Object.entries(result.ranking || {}).map(([signal, value]) => (
                          <li key={signal}>
                            <span>{rankingLabels[signal] || signal}</span>
                            <strong>+{value}</strong>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                </article>
              ))}

          </section>
        )}

      </main>

      <footer>
        <span>© 2026 YEXA</span>
        <span>Built with our own search technology</span>
      </footer>

    </div>
  );
}

export default App;
