package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

type server struct {
	db *sql.DB
}

func runServe() {
	db, err := openDB()
	if err != nil {
		fmt.Fprintf(os.Stderr, "reelm: open db: %v\n", err)
		os.Exit(1)
	}
	if err := initSchema(db); err != nil {
		fmt.Fprintf(os.Stderr, "reelm: init schema: %v\n", err)
		os.Exit(1)
	}
	s := &server{db: db}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /search", s.handleSearch)
	mux.HandleFunc("GET /stats", s.handleStats)
	mux.HandleFunc("POST /save", s.handleSave)
	mux.HandleFunc("POST /transcript", s.handleTranscript)
	mux.HandleFunc("POST /wipe", s.handleWipe)

	addr := fmt.Sprintf("127.0.0.1:%d", port)
	fmt.Printf("reeLm server listening on http://%s\n", addr)
	if err := http.ListenAndServe(addr, corsMiddleware(mux)); err != nil {
		fmt.Fprintf(os.Stderr, "reelm: %v\n", err)
		os.Exit(1)
	}
}

func originOK(r *http.Request) bool {
	origin := r.Header.Get("Origin")
	return origin == "" || strings.HasPrefix(origin, "chrome-extension://")
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !originOK(r) {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		origin := r.Header.Get("Origin")
		if strings.HasPrefix(origin, "chrome-extension://") {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
			w.Header().Set("Access-Control-Allow-Private-Network", "true")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (s *server) jsonReply(w http.ResponseWriter, code int, v any) {
	data, _ := json.Marshal(v)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	w.Write(data)
}

func (s *server) handleStats(w http.ResponseWriter, _ *http.Request) {
	var total, indexed int
	s.db.QueryRow("SELECT COUNT(*), COALESCE(SUM(has_transcript),0) FROM videos").Scan(&total, &indexed)
	s.jsonReply(w, 200, map[string]int{"total": total, "indexed": indexed})
}

func (s *server) handleSearch(w http.ResponseWriter, r *http.Request) {
	q := strings.TrimSpace(r.URL.Query().Get("q"))
	if q == "" {
		s.jsonReply(w, 400, map[string]any{"results": []any{}, "error": "Missing query"})
		return
	}
	rows, err := s.db.Query(`
		SELECT v.title, s.video_id, s.start_secs, v.indexed_at
		FROM segments s
		JOIN videos v ON v.id = s.video_id
		WHERE segments MATCH ?
		GROUP BY s.video_id
		ORDER BY rank
		LIMIT 25
	`, q)
	if err != nil {
		s.jsonReply(w, 500, map[string]any{"results": []any{}, "error": err.Error()})
		return
	}
	defer rows.Close()

	type result struct {
		Title     string `json:"title"`
		VideoID   string `json:"videoId"`
		StartSecs int    `json:"startSecs"`
		SavedAt   int64  `json:"savedAt"`
		URL       string `json:"url"`
	}
	var results []result
	for rows.Next() {
		var res result
		rows.Scan(&res.Title, &res.VideoID, &res.StartSecs, &res.SavedAt)
		res.URL = fmt.Sprintf("https://youtube.com/watch?v=%s&t=%d", res.VideoID, res.StartSecs)
		results = append(results, res)
	}
	if results == nil {
		results = []result{}
	}
	s.jsonReply(w, 200, map[string]any{"results": results})
}

func (s *server) handleSave(w http.ResponseWriter, r *http.Request) {
	var body struct {
		VideoID     string          `json:"videoId"`
		Title       string          `json:"title"`
		CurrentTime float64         `json:"currentTime"`
		Segments    json.RawMessage `json:"segments"` // nil if key absent (old extension)
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		s.jsonReply(w, 400, map[string]any{"message": "Bad request"})
		return
	}

	videoID := strings.TrimSpace(body.VideoID)
	title := strings.TrimSpace(body.Title)
	if title == "" {
		title = "Unknown"
	}
	saveTsSecs := int(body.CurrentTime)

	if videoID == "" {
		s.jsonReply(w, 400, map[string]any{"message": "Missing videoId"})
		return
	}

	var existingID string
	s.db.QueryRow("SELECT id FROM videos WHERE id=?", videoID).Scan(&existingID)
	if existingID != "" {
		s.jsonReply(w, 200, map[string]any{
			"message":  fmt.Sprintf("Already saved — %s", title),
			"new_save": false,
		})
		return
	}

	if _, err := s.db.Exec(
		"INSERT INTO videos(id, title, save_ts_secs) VALUES (?,?,?)",
		videoID, title, saveTsSecs,
	); err != nil {
		s.jsonReply(w, 500, map[string]any{"message": err.Error()})
		return
	}

	// Legacy yt-dlp fallback only when old extension sends no segments key.
	if body.Segments == nil {
		go s.fetchAndIndex(videoID, title)
	}

	mins, secs := saveTsSecs/60, saveTsSecs%60
	s.jsonReply(w, 200, map[string]any{
		"message":  fmt.Sprintf("Saved @ %d:%02d — %s", mins, secs, title),
		"new_save": true,
	})
}

func (s *server) fetchAndIndex(videoID, title string) {
	segs, err := fetchSegments(videoID)
	if err != nil {
		fmt.Printf("Transcript unavailable for %s: %v\n", videoID, err)
		return
	}
	if len(segs) == 0 {
		fmt.Printf("No transcript for %s: %s\n", videoID, title)
		return
	}
	s.writeSegments(videoID, segs)
	fmt.Printf("Indexed %d segments: %s\n", len(segs), title)
}

func (s *server) handleTranscript(w http.ResponseWriter, r *http.Request) {
	var body struct {
		VideoID  string `json:"videoId"`
		Segments []struct {
			Start float64 `json:"start"`
			Text  string  `json:"text"`
		} `json:"segments"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		s.jsonReply(w, 400, map[string]any{"ok": false})
		return
	}

	videoID := strings.TrimSpace(body.VideoID)
	if videoID != "" && len(body.Segments) > 0 {
		var hasTranscript int
		err := s.db.QueryRow("SELECT has_transcript FROM videos WHERE id=?", videoID).Scan(&hasTranscript)
		if err == nil && hasTranscript == 0 {
			var segs []segment
			for _, bs := range body.Segments {
				if bs.Text != "" {
					segs = append(segs, segment{start: bs.Start, text: bs.Text})
				}
			}
			s.writeSegments(videoID, segs)
			fmt.Printf("Transcript from browser: %s (%d segs)\n", videoID, len(segs))
		}
	}
	s.jsonReply(w, 200, map[string]any{"ok": true})
}

func (s *server) handleWipe(w http.ResponseWriter, _ *http.Request) {
	backup := strings.TrimSuffix(dbFilePath(), ".db") +
		".backup-" + time.Now().Format("20060102-150405") + ".db"
	if err := copyFile(dbFilePath(), backup); err != nil {
		s.jsonReply(w, 500, map[string]any{"error": "backup failed: " + err.Error()})
		return
	}
	var deleted int
	s.db.QueryRow("SELECT COUNT(*) FROM videos").Scan(&deleted)
	s.db.Exec("DELETE FROM segments")
	s.db.Exec("DELETE FROM videos")
	s.db.Exec("VACUUM")
	fmt.Printf("Wiped %d videos — backup at %s\n", deleted, backup)
	s.jsonReply(w, 200, map[string]int{"deleted": deleted})
}

func (s *server) writeSegments(videoID string, segs []segment) {
	tx, err := s.db.Begin()
	if err != nil {
		return
	}
	tx.Exec("UPDATE videos SET has_transcript=1 WHERE id=?", videoID)
	for _, seg := range segs {
		tx.Exec(
			"INSERT INTO segments(video_id, start_secs, text) VALUES (?,?,?)",
			videoID, int(seg.start), seg.text,
		)
	}
	tx.Commit()
}
