package main

import (
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

func TestAllowlistMatching(t *testing.T) {
	policy := parseAllowedHosts("api.github.com, *.npmjs.org,localhost")
	tests := []struct {
		name string
		host string
		want bool
	}{
		{"exact host", "api.github.com", true},
		{"case insensitive with port", "API.GITHUB.COM:443", true},
		{"wildcard child", "registry.npmjs.org", true},
		{"wildcard grandchild", "a.b.npmjs.org", true},
		{"wildcard root rejected", "npmjs.org", false},
		{"unknown host rejected", "evil.example.com", false},
		{"empty host rejected", "", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := policy.Allows(tt.host); got != tt.want {
				t.Fatalf("Allows(%q) = %v, want %v", tt.host, got, tt.want)
			}
		})
	}
}

func TestHTTPProxyFiltersMockSandbox(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("sandbox-ok"))
	}))
	t.Cleanup(upstream.Close)

	proxy := httptest.NewServer(newProxy(parseAllowedHosts("localhost")))
	t.Cleanup(proxy.Close)

	client := proxyClient(t, proxy.URL)
	allowedURL := localhostURL(t, upstream.URL)
	resp, err := client.Get(allowedURL)
	if err != nil {
		t.Fatalf("allowed request failed: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("allowed status = %d, want 200", resp.StatusCode)
	}
	body, _ := io.ReadAll(resp.Body)
	if string(body) != "sandbox-ok" {
		t.Fatalf("allowed body = %q", body)
	}

	blocked, err := client.Get("http://evil.example.com")
	if err != nil {
		t.Fatalf("blocked request returned transport error: %v", err)
	}
	defer blocked.Body.Close()
	if blocked.StatusCode != http.StatusForbidden {
		t.Fatalf("blocked status = %d, want 403", blocked.StatusCode)
	}

	metrics, err := http.Get(proxy.URL + "/metrics")
	if err != nil {
		t.Fatalf("metrics request failed: %v", err)
	}
	defer metrics.Body.Close()
	metricsBody, _ := io.ReadAll(metrics.Body)
	for _, name := range []string{"requests_total 2", "blocked_total 1", "latency_histogram_count 2"} {
		if !strings.Contains(string(metricsBody), name) {
			t.Fatalf("metrics missing %q in:\n%s", name, metricsBody)
		}
	}
}

func TestControlEndpointsAndConnectBlock(t *testing.T) {
	proxy := httptest.NewServer(newProxy(parseAllowedHosts("api.github.com")))
	t.Cleanup(proxy.Close)

	health, err := http.Get(proxy.URL + "/health")
	if err != nil {
		t.Fatalf("health request failed: %v", err)
	}
	defer health.Body.Close()
	if health.StatusCode != http.StatusOK {
		t.Fatalf("health status = %d, want 200", health.StatusCode)
	}

	proxyURL, err := url.Parse(proxy.URL)
	if err != nil {
		t.Fatal(err)
	}
	conn, err := net.Dial("tcp", proxyURL.Host)
	if err != nil {
		t.Fatalf("dial proxy: %v", err)
	}
	defer conn.Close()
	_, _ = conn.Write([]byte("CONNECT evil.example.com:443 HTTP/1.1\r\nHost: evil.example.com:443\r\n\r\n"))
	buf := make([]byte, 128)
	n, err := conn.Read(buf)
	if err != nil {
		t.Fatalf("read CONNECT response: %v", err)
	}
	if !strings.Contains(string(buf[:n]), "403 Forbidden") {
		t.Fatalf("CONNECT response = %q, want 403", buf[:n])
	}
}

func proxyClient(t *testing.T, rawProxyURL string) *http.Client {
	t.Helper()
	proxyURL, err := url.Parse(rawProxyURL)
	if err != nil {
		t.Fatal(err)
	}
	return &http.Client{Transport: &http.Transport{Proxy: http.ProxyURL(proxyURL)}}
}

func localhostURL(t *testing.T, rawURL string) string {
	t.Helper()
	parsed, err := url.Parse(rawURL)
	if err != nil {
		t.Fatal(err)
	}
	_, port, err := net.SplitHostPort(parsed.Host)
	if err != nil {
		t.Fatal(err)
	}
	parsed.Host = net.JoinHostPort("localhost", port)
	return parsed.String()
}
