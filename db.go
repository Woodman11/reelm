package main

import (
	"database/sql"
	"io"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

const port = 7799

func dbDataDir() string {
	h, _ := os.UserHomeDir()
	return filepath.Join(h, "Library", "Application Support", "Reelm")
}

func logDir() string {
	h, _ := os.UserHomeDir()
	return filepath.Join(h, "Library", "Logs", "reelm")
}

func dbFilePath() string {
	return filepath.Join(dbDataDir(), "videos.db")
}

func execDir() string {
	exe, err := os.Executable()
	if err != nil {
		return "."
	}
	return filepath.Dir(exe)
}

func migrateLegacy() {
	dst := dbFilePath()
	if _, err := os.Stat(dst); err == nil {
		return
	}
	_ = os.MkdirAll(filepath.Dir(dst), 0o755)
	h, _ := os.UserHomeDir()
	for _, src := range []string{
		filepath.Join(h, "Library", "Application Support", "MyYouTubeSearch", "videos.db"),
		filepath.Join(execDir(), "videos.db"),
	} {
		if _, err := os.Stat(src); err == nil {
			_ = copyFile(src, dst)
			return
		}
	}
}

func openDB() (*sql.DB, error) {
	migrateLegacy()
	_ = os.MkdirAll(logDir(), 0o755)
	if err := os.MkdirAll(dbDataDir(), 0o755); err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlite", dbFilePath())
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	if _, err := db.Exec("PRAGMA journal_mode=WAL"); err != nil {
		db.Close()
		return nil, err
	}
	db.Exec("PRAGMA wal_autocheckpoint=1000")
	return db, nil
}

func initSchema(db *sql.DB) error {
	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS videos (
			id             TEXT PRIMARY KEY,
			title          TEXT,
			save_ts_secs   INTEGER,
			indexed_at     INTEGER DEFAULT (strftime('%s','now')),
			has_transcript INTEGER DEFAULT 0
		);
		CREATE VIRTUAL TABLE IF NOT EXISTS segments USING fts5(
			video_id   UNINDEXED,
			start_secs UNINDEXED,
			text,
			tokenize   = "porter unicode61"
		);
	`); err != nil {
		return err
	}
	// Idempotent migration — errors with "duplicate column name" after the first run.
	db.Exec("ALTER TABLE videos ADD COLUMN retry_count INTEGER DEFAULT 0")
	return nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}
