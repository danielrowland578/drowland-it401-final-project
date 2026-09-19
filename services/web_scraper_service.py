import re
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import quote_plus

import requests


class WebScraperService:
    """Lightweight Bing HTML scraper that enriches threat records with public context."""

    def __init__(self, timeout=5, max_workers=6):
        self.timeout = timeout
        self.max_workers = max_workers
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }

    def enrich_threats(self, threats):
        def enrich_one(threat):
            entry = dict(threat)
            scraped = self.scrape_threat(entry)
            if scraped:
                entry["web_summary"] = scraped.get("summary")
                entry["web_reference"] = scraped.get("reference_url")
                entry["reference_title"] = scraped.get("reference_title")
                entry["web_risk_score"] = scraped.get("risk_score")
                entry["web_risk_label"] = scraped.get("risk_label")
                entry["source"] = f"{entry.get('source', 'Public source')} / live scrape"
            return entry

        # Search in parallel, but map keeps cards in their original feed order.
        worker_count = min(self.max_workers, max(len(threats), 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            return list(executor.map(enrich_one, threats))

    def scrape_threat(self, threat):
        title = threat.get("title") or "cybersecurity threat"
        category = threat.get("category") or "cybersecurity"
        query = f'"{title}" "{category}" cybersecurity'
        url = f"https://www.bing.com/search?q={quote_plus(query)}"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException:
            return None

        text = response.text
        matches = re.findall(
            r'<li[^>]+class="[^"]*b_algo[^"]*".*?'
            r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'<div[^>]+class="[^"]*b_caption[^"]*".*?<p[^>]*>(.*?)</p>',
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if not matches:
            return None

        reference_url, reference_title, snippet = max(
            matches,
            key=lambda result: self._relevance_score(threat, result[1], result[2]),
        )
        if self._relevance_score(threat, reference_title, snippet) == 0:
            return None
        reference_url = unescape(reference_url)
        cleaned_title = self._clean_text(reference_title)
        cleaned_snippet = self._clean_text(snippet)
        if not cleaned_snippet:
            return None

        risk_score = self._risk_score(threat, cleaned_title, cleaned_snippet)
        return {
            "reference_title": cleaned_title or title,
            "reference_url": reference_url,
            "summary": cleaned_snippet[:260],
            "risk_score": risk_score,
            "risk_label": self._risk_label(risk_score),
        }

    @staticmethod
    def _relevance_score(threat, reference_title, summary):
        stop_words = {
            "the", "and", "for", "with", "use", "new", "detected", "legacy",
            "version", "campaign", "activity", "incident",
        }
        threat_terms = {
            term
            for value in (threat.get("title", ""), threat.get("category", ""), threat.get("indicators", ""))
            for term in re.findall(r"[a-z0-9]{3,}", str(value).lower())
            if term not in stop_words
        }
        result_terms = set(re.findall(r"[a-z0-9]{3,}", f"{reference_title} {summary}".lower()))
        return len(threat_terms & result_terms)

    @staticmethod
    def _risk_score(threat, reference_title, summary):
        severity_points = {"low": 25, "medium": 45, "high": 70, "critical": 88}
        score = severity_points.get(str(threat.get("severity", "")).lower(), 35)
        evidence = f"{reference_title} {summary}".lower()
        risk_terms = (
            "attack", "breach", "botnet", "credential", "exploit", "malware",
            "phishing", "ransomware", "vulnerability", "command and control",
        )
        score += min(sum(3 for term in risk_terms if term in evidence), 12)
        if threat.get("indicators"):
            score += 2
        return min(score, 100)

    @staticmethod
    def _risk_label(score):
        if score >= 85:
            return "Critical"
        if score >= 65:
            return "High"
        if score >= 40:
            return "Moderate"
        return "Low"

    @staticmethod
    def _clean_text(value):
        value = unescape(value)
        value = re.sub(r"<.*?>", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()
