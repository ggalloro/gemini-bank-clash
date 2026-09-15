package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"
)

type LedgerTransaction struct {
	ID           any     `json:"id"`
	AccountID    any     `json:"account_id"`
	Type         string  `json:"type"`
	Amount       any     `json:"amount"`
	Counterparty *string `json:"counterparty"`
	Description  *string `json:"description"`
	CreatedAt    *string `json:"created_at"`
}

type DetailTransaction struct {
	Amount       any     `json:"amount"`
	Counterparty *string `json:"counterparty"`
	Date         *string `json:"date"`
	Description  *string `json:"description"`
	ID           any     `json:"id"`
	Type         string  `json:"type"`
}

type StatementResponse struct {
	AccountID    string              `json:"account_id"`
	Count        int                 `json:"count"`
	From         *string             `json:"from"`
	To           *string             `json:"to"`
	Transactions []DetailTransaction `json:"transactions"`
}

type MonthSummary struct {
	Month    string  `json:"month"`
	Net      float64 `json:"net"`
	TotalIn  float64 `json:"total_in"`
	TotalOut float64 `json:"total_out"`
}

type SummaryResponse struct {
	AccountID string         `json:"account_id"`
	Months    []MonthSummary `json:"months"`
}

var httpClient = &http.Client{
	Timeout: 10 * time.Second,
}

func fetchTransactions(ledgerURL, accountID string, dateFrom, dateTo *string) []LedgerTransaction {
	base := strings.TrimRight(ledgerURL, "/")
	endpoint := base + "/internal/transactions"
	u, err := url.Parse(endpoint)
	if err != nil {
		return []LedgerTransaction{}
	}

	q := u.Query()
	q.Set("account_id", accountID)
	if dateFrom != nil && *dateFrom != "" {
		q.Set("from", *dateFrom)
	}
	if dateTo != nil && *dateTo != "" {
		q.Set("to", *dateTo)
	}
	u.RawQuery = q.Encode()

	resp, err := httpClient.Get(u.String())
	if err != nil {
		return []LedgerTransaction{}
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return []LedgerTransaction{}
	}

	var data struct {
		Transactions []LedgerTransaction `json:"transactions"`
	}
	dec := json.NewDecoder(resp.Body)
	dec.UseNumber()
	if err := dec.Decode(&data); err != nil {
		return []LedgerTransaction{}
	}

	if data.Transactions == nil {
		return []LedgerTransaction{}
	}
	return data.Transactions
}

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(data)
}

func handleHealthz(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func handleStatements(w http.ResponseWriter, r *http.Request, ledgerURL string) {
	accountID := r.PathValue("id")
	var dateFrom *string
	if r.URL.Query().Has("from") {
		v := r.URL.Query().Get("from")
		dateFrom = &v
	}
	var dateTo *string
	if r.URL.Query().Has("to") {
		v := r.URL.Query().Get("to")
		dateTo = &v
	}
	typeFilter := r.URL.Query().Get("type")

	txns := fetchTransactions(ledgerURL, accountID, dateFrom, dateTo)

	outList := make([]DetailTransaction, 0)
	for _, t := range txns {
		if typeFilter != "" && t.Type != typeFilter {
			continue
		}
		row := DetailTransaction{
			Amount:       t.Amount,
			Counterparty: t.Counterparty,
			Date:         t.CreatedAt,
			Description:  t.Description,
			ID:           t.ID,
			Type:         t.Type,
		}
		outList = append(outList, row)
	}

	resp := StatementResponse{
		AccountID:    accountID,
		Count:        len(outList),
		From:         dateFrom,
		To:           dateTo,
		Transactions: outList,
	}

	writeJSON(w, http.StatusOK, resp)
}

func parseMonth(s string) (string, error) {
	if s == "" {
		return "", fmt.Errorf("empty date")
	}
	clean := strings.Replace(s, "Z", "+00:00", 1)
	layouts := []string{
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02T15:04:05.999999999-07:00",
		"2006-01-02T15:04:05.999999999",
		"2006-01-02T15:04:05",
		"2006-01-02 15:04:05",
		"2006-01-02",
	}
	for _, l := range layouts {
		if t, err := time.Parse(l, s); err == nil {
			return fmt.Sprintf("%04d-%02d", t.Year(), t.Month()), nil
		}
		if t, err := time.Parse(l, clean); err == nil {
			return fmt.Sprintf("%04d-%02d", t.Year(), t.Month()), nil
		}
	}
	return "", fmt.Errorf("unrecognized format: %s", s)
}

func toFloat64(val any) float64 {
	if val == nil {
		return 0.0
	}
	switch v := val.(type) {
	case json.Number:
		if f, err := v.Float64(); err == nil {
			return f
		}
	case float64:
		return v
	case int:
		return float64(v)
	case int64:
		return float64(v)
	case string:
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			return f
		}
	}
	return 0.0
}

func round2(val float64) float64 {
	return math.Round(val*100) / 100
}

type bucket struct {
	totalIn  float64
	totalOut float64
}

func handleSummary(w http.ResponseWriter, r *http.Request, ledgerURL string) {
	accountID := r.PathValue("id")
	monthsN := 6
	if q := r.URL.Query().Get("months"); q != "" {
		if n, err := strconv.Atoi(q); err == nil {
			monthsN = n
		}
	}

	txns := fetchTransactions(ledgerURL, accountID, nil, nil)

	buckets := make(map[string]*bucket)
	for _, t := range txns {
		if t.CreatedAt == nil || *t.CreatedAt == "" {
			continue
		}
		key, err := parseMonth(*t.CreatedAt)
		if err != nil {
			continue
		}
		b, ok := buckets[key]
		if !ok {
			b = &bucket{}
			buckets[key] = b
		}
		amt := toFloat64(t.Amount)
		switch t.Type {
		case "deposit", "payment_in":
			b.totalIn += amt
		case "payment_out":
			b.totalOut += amt
		}
	}

	keys := make([]string, 0, len(buckets))
	for k := range buckets {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		return keys[i] > keys[j]
	})

	if monthsN < 0 {
		n := len(keys) + monthsN
		if n < 0 {
			n = 0
		}
		keys = keys[:n]
	} else {
		if monthsN > len(keys) {
			monthsN = len(keys)
		}
		keys = keys[:monthsN]
	}

	monthsList := make([]MonthSummary, 0, len(keys))
	for _, k := range keys {
		b := buckets[k]
		tin := round2(b.totalIn)
		tout := round2(b.totalOut)
		net := round2(tin - tout)
		monthsList = append(monthsList, MonthSummary{
			Month:    k,
			Net:      net,
			TotalIn:  tin,
			TotalOut: tout,
		})
	}

	resp := SummaryResponse{
		AccountID: accountID,
		Months:    monthsList,
	}

	writeJSON(w, http.StatusOK, resp)
}

func main() {
	ledgerURL := os.Getenv("LEDGER_URL")
	if ledgerURL == "" {
		ledgerURL = "http://localhost:8082"
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8083"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", handleHealthz)
	mux.HandleFunc("GET /statements/{id}/summary", func(w http.ResponseWriter, r *http.Request) {
		handleSummary(w, r, ledgerURL)
	})
	mux.HandleFunc("GET /statements/{id}", func(w http.ResponseWriter, r *http.Request) {
		handleStatements(w, r, ledgerURL)
	})

	server := &http.Server{
		Addr:         ":" + port,
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
	}

	log.Printf("Starting statements service on port %s, LEDGER_URL=%s", port, ledgerURL)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
}
