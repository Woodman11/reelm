package main

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

const (
	logRotateBytes = 1_000_000
	logKeepLines   = 200
	maxRetries     = 5
)

func runMaintain() {
	db, err := openDB()
	if err != nil {
		fmt.Fprintf(os.Stderr, "reelm maintain: %v\n", err)
		os.Exit(1)
	}
	defer db.Close()
	if err := initSchema(db); err != nil {
		fmt.Fprintf(os.Stderr, "reelm maintain: init schema: %v\n", err)
		os.Exit(1)
	}

	mlog := func(msg string) {
		fmt.Printf("[%s] %s\n", time.Now().Format("2006-01-02 15:04:05"), msg)
	}

	statsLine := func(label string) {
		var total, indexed int
		var segs int64
		db.QueryRow("SELECT COUNT(*), COALESCE(SUM(has_transcript),0) FROM videos").Scan(&total, &indexed)
		db.QueryRow("SELECT COUNT(*) FROM segments").Scan(&segs)
		sizeKB := int64(0)
		if info, err := os.Stat(dbFilePath()); err == nil {
			sizeKB = info.Size() / 1024
		}
		mlog(fmt.Sprintf("%s%d videos (%d indexed, %d missing) | %d segments | %d KB",
			label, total, indexed, total-indexed, segs, sizeKB))
	}

	mlog("=== maintenance start ===")
	statsLine("Stats: ")

	// Retry missing transcripts (skip ones that have already failed maxRetries times)
	rows, _ := db.Query("SELECT id, title FROM videos WHERE has_transcript=0 AND retry_count < ?", maxRetries)
	type vid struct{ id, title string }
	var missing []vid
	for rows.Next() {
		var v vid
		rows.Scan(&v.id, &v.title)
		missing = append(missing, v)
	}
	rows.Close()

	var skipped int
	db.QueryRow("SELECT COUNT(*) FROM videos WHERE has_transcript=0 AND retry_count >= ?", maxRetries).Scan(&skipped)
	if skipped > 0 {
		mlog(fmt.Sprintf("Retry: %d video(s) skipped (exceeded %d retries — likely unavailable)", skipped, maxRetries))
	}

	if len(missing) == 0 {
		mlog("Retry: no videos missing transcripts")
	} else {
		mlog(fmt.Sprintf("Retry: %d video(s) with no transcript", len(missing)))
		recovered := 0
		for _, v := range missing {
			segs, err := fetchSegments(v.id)
			if err != nil {
				db.Exec("UPDATE videos SET retry_count = retry_count + 1 WHERE id=?", v.id)
				mlog(fmt.Sprintf("  FAIL %s — %s: %v", v.id, v.title, err))
				continue
			}
			if len(segs) == 0 {
				db.Exec("UPDATE videos SET retry_count = retry_count + 1 WHERE id=?", v.id)
				mlog(fmt.Sprintf("  FAIL %s — %s: no subtitles available", v.id, v.title))
				continue
			}
			tx, _ := db.Begin()
			// Re-check inside tx in case the server's fetchAndIndex already wrote segments.
			var hasTranscript int
			if err := tx.QueryRow("SELECT has_transcript FROM videos WHERE id=?", v.id).Scan(&hasTranscript); err != nil || hasTranscript != 0 {
				tx.Rollback()
				mlog(fmt.Sprintf("  SKIP %s — %s: already indexed by server", v.id, v.title))
				continue
			}
			tx.Exec("UPDATE videos SET has_transcript=1 WHERE id=?", v.id)
			for _, seg := range segs {
				tx.Exec("INSERT INTO segments(video_id, start_secs, text) VALUES (?,?,?)",
					v.id, int(seg.start), seg.text)
			}
			tx.Commit()
			mlog(fmt.Sprintf("  OK  %s — %s (%d segments)", v.id, v.title, len(segs)))
			recovered++
		}
		mlog(fmt.Sprintf("Retry: recovered %d/%d", recovered, len(missing)))
	}

	db.Exec("INSERT INTO segments(segments) VALUES('optimize')")
	mlog("FTS5 optimize: done")

	db.Exec("VACUUM")
	mlog("VACUUM: done")

	if _, err := db.Exec("PRAGMA wal_checkpoint(TRUNCATE)"); err == nil {
		mlog("WAL checkpoint: done")
	}

	statsLine("Stats: ")

	exDir := execDir()
	rotateLog(filepath.Join(exDir, "server.log"), mlog)
	rotateLog(filepath.Join(exDir, "maintain.log"), mlog)

	mlog("=== maintenance done ===")
}

func rotateLog(path string, mlog func(string)) {
	info, err := os.Stat(path)
	if err != nil || info.Size() < logRotateBytes {
		return
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	tail := data
	if len(data) > 256_000 {
		tail = data[len(data)-256_000:]
	}
	lines := bytes.Split(tail, []byte("\n"))
	if len(lines) > logKeepLines {
		lines = lines[len(lines)-logKeepLines:]
	}
	out := append([]byte("--- log rotated by reelm maintain ---\n"), bytes.Join(lines, []byte("\n"))...)
	if err := os.WriteFile(path, out, 0o644); err == nil {
		mlog(fmt.Sprintf("Rotated %s (was %d KB)", filepath.Base(path), info.Size()/1024))
	}
}
