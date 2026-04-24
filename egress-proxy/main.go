package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"sync/atomic"
	"time"
)

type allowlist struct {
	exact    map[string]struct{}
	wildcard []string
}

func parseAllowedHosts(raw string) allowlist {
	policy := allowlist{exact: map[string]struct{}{}}
	for _, entry := range strings.Split(raw, ",") {
		host := normalizeHost(entry)
		if host == "" {
			continue
		}
		if strings.HasPrefix(host, "*.") {
			policy.wildcard = append(policy.wildcard, strings.TrimPrefix(host, "*."))
			continue
		}
		policy.exact[host] = struct{}{}
	}
	return policy
}

func (a allowlist) Allows(host string) bool {
	host = normalizeHost(host)
	if host == "" {
		return false
	}
	if _, ok := a.exact[host]; ok {
		return true
	}
	for _, suffix := range a.wildcard {
		if host != suffix && strings.HasSuffix(host, "."+suffix) {
			return true
		}
	}
	return false
}

func normalizeHost(raw string) string {
	host := strings.ToLower(strings.TrimSpace(raw))
	if host == "" {
		return ""
	}
	if parsed, _, err := net.SplitHostPort(host); err == nil {
		host = parsed
	}
	host = strings.Trim(host, "[]")
	host = strings.TrimSuffix(host, ".")
	return host
}

type proxyMetrics struct {
	requests      atomic.Uint64
	blocked       atomic.Uint64
	latencyCount  atomic.Uint64
	latencyMicros atomic.Uint64
	buckets       [5]atomic.Uint64
}

func (m *proxyMetrics) Observe(duration time.Duration) {
	m.latencyCount.Add(1)
	m.latencyMicros.Add(uint64(duration.Microseconds()))
	seconds := duration.Seconds()
	for index, limit := range []float64{0.005, 0.01, 0.025, 0.05, 0.1} {
		if seconds <= limit {
			m.buckets[index].Add(1)
		}
	}
}

func (m *proxyMetrics) ServeHTTP(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	fmt.Fprintf(w, "# TYPE requests_total counter\nrequests_total %d\n", m.requests.Load())
	fmt.Fprintf(w, "# TYPE blocked_total counter\nblocked_total %d\n", m.blocked.Load())
	fmt.Fprintln(w, "# TYPE latency_histogram histogram")
	for index, limit := range []string{"0.005", "0.01", "0.025", "0.05", "0.1"} {
		fmt.Fprintf(w, "latency_histogram_bucket{le=%q} %d\n", limit, m.buckets[index].Load())
	}
	fmt.Fprintf(w, "latency_histogram_bucket{le=\"+Inf\"} %d\n", m.latencyCount.Load())
	fmt.Fprintf(w, "latency_histogram_sum %.6f\n", float64(m.latencyMicros.Load())/1_000_000)
	fmt.Fprintf(w, "latency_histogram_count %d\n", m.latencyCount.Load())
}

type egressProxy struct {
	allowed   allowlist
	metrics   *proxyMetrics
	transport *http.Transport
	dialer    net.Dialer
}

func newProxy(allowed allowlist) http.Handler {
	return &egressProxy{
		allowed: allowed,
		metrics: &proxyMetrics{},
		transport: &http.Transport{
			Proxy:                 nil,
			DialContext:           (&net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}).DialContext,
			ResponseHeaderTimeout: 30 * time.Second,
			IdleConnTimeout:       90 * time.Second,
		},
		dialer: net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second},
	}
}

func (p *egressProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodConnect && !r.URL.IsAbs() {
		switch r.URL.Path {
		case "/health":
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("ok\n"))
		case "/metrics":
			p.metrics.ServeHTTP(w, r)
		default:
			http.NotFound(w, r)
		}
		return
	}

	start := time.Now()
	p.metrics.requests.Add(1)
	defer p.metrics.Observe(time.Since(start))

	if r.Method == http.MethodConnect {
		p.handleConnect(w, r)
		return
	}
	p.handleHTTP(w, r)
}

func (p *egressProxy) handleHTTP(w http.ResponseWriter, r *http.Request) {
	host := r.URL.Host
	if host == "" {
		host = r.Host
	}
	if !p.allowed.Allows(host) {
		p.writeBlocked(w, host)
		return
	}

	outbound := r.Clone(r.Context())
	outbound.RequestURI = ""
	outbound.Header = r.Header.Clone()
	outbound.Header.Del("Proxy-Connection")

	response, err := p.transport.RoundTrip(outbound)
	if err != nil {
		http.Error(w, "upstream unavailable", http.StatusBadGateway)
		return
	}
	defer response.Body.Close()
	copyHeader(w.Header(), response.Header)
	w.WriteHeader(response.StatusCode)
	_, _ = io.Copy(w, response.Body)
}

func (p *egressProxy) handleConnect(w http.ResponseWriter, r *http.Request) {
	if !p.allowed.Allows(r.Host) {
		p.writeBlocked(w, r.Host)
		return
	}

	clientConn, buffered, err := http.NewResponseController(w).Hijack()
	if err != nil {
		http.Error(w, "hijack failed", http.StatusInternalServerError)
		return
	}
	defer clientConn.Close()

	targetConn, err := p.dialer.DialContext(r.Context(), "tcp", r.Host)
	if err != nil {
		_, _ = clientConn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}
	defer targetConn.Close()

	_, _ = clientConn.Write([]byte("HTTP/1.1 200 Connection Established\r\n\r\n"))
	done := make(chan struct{}, 2)
	go copyAndSignal(targetConn, buffered, done)
	go copyAndSignal(clientConn, targetConn, done)
	<-done
}

func (p *egressProxy) writeBlocked(w http.ResponseWriter, host string) {
	p.metrics.blocked.Add(1)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusForbidden)
	_, _ = fmt.Fprintf(w, `{"error":"egress blocked","host":%q}`+"\n", normalizeHost(host))
}

func copyHeader(dst, src http.Header) {
	for key, values := range src {
		for _, value := range values {
			dst.Add(key, value)
		}
	}
}

func copyAndSignal(dst io.Writer, src io.Reader, done chan<- struct{}) {
	_, _ = io.Copy(dst, src)
	done <- struct{}{}
}

func main() {
	allowed := parseAllowedHosts(os.Getenv("ALLOWED_HOSTS"))
	port := os.Getenv("PORT")
	if port == "" {
		port = "3128"
	}
	server := &http.Server{
		Addr:              ":" + port,
		Handler:           newProxy(allowed),
		ReadHeaderTimeout: 10 * time.Second,
		BaseContext: func(net.Listener) context.Context {
			return context.Background()
		},
	}
	log.Printf("egress proxy listening on %s", server.Addr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("egress proxy failed: %v", err)
	}
}
