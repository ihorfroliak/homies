"""Saved-search and alert metrics (TASK-014). Counts and buckets only: no
label ever carries a user, listing, search or place id, a query, a
fingerprint or an address."""

from prometheus_client import Counter, Gauge, Histogram

SAVED_LISTINGS = Counter("homies_saved_listings_total", "Saved-listing actions", ["action"])
SAVED_SEARCHES = Counter("homies_saved_searches_total", "Saved-search actions", ["action"])
SAVED_SEARCHES_ACTIVE = Gauge("homies_saved_searches_active",
                              "Saved searches active with notifications on")
MATCHES_CREATED = Counter("homies_saved_search_match_created_total",
                          "Saved-search matches recorded")
DELIVERIES = Counter("homies_alert_delivery_total", "Alert deliveries finished",
                     ["channel", "status"])
WORKER_BATCHES = Counter("homies_saved_search_worker_batch_total",
                         "Alert worker batches", ["stage"])
WORK_ITEMS = Counter("homies_saved_search_work_items_total",
                     "Public-generation work items finished", ["outcome"])
INVALID_QUERIES = Counter("homies_saved_search_invalid_query_total",
                          "Stored queries found INVALID during matching")
CANDIDATES = Histogram("homies_saved_search_candidates",
                       "Candidate saved searches per new public generation",
                       buckets=(0, 1, 5, 10, 50, 100, 500, 1000, 5000, 10000))
UNSUBSCRIBES = Counter("homies_unsubscribe_requests_total", "Unsubscribe requests", ["outcome"])
