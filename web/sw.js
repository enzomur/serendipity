/**
 * Serendipity Service Worker
 *
 * Caches app shell and loaded shards for offline reading.
 * Cache versioned against manifest version.
 */

const CACHE_PREFIX = 'serendipity-';
const APP_SHELL = [
    './',
    './index.html',
    './app.js',
    './style.css',
    './manifest.webmanifest'
];

let CACHE_VERSION = 'v1';

// Fetch manifest to get version
async function getManifestVersion() {
    try {
        const res = await fetch('./data/manifest.json');
        if (res.ok) {
            const manifest = await res.json();
            return manifest.version || 'v1';
        }
    } catch (e) {
        console.warn('Could not fetch manifest for version:', e);
    }
    return 'v1';
}

function getCacheName() {
    return CACHE_PREFIX + CACHE_VERSION;
}

// Install: cache app shell
self.addEventListener('install', (event) => {
    event.waitUntil(
        (async () => {
            CACHE_VERSION = await getManifestVersion();
            const cache = await caches.open(getCacheName());
            await cache.addAll(APP_SHELL);
            self.skipWaiting();
        })()
    );
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        (async () => {
            CACHE_VERSION = await getManifestVersion();
            const cacheNames = await caches.keys();
            await Promise.all(
                cacheNames
                    .filter(name => name.startsWith(CACHE_PREFIX) && name !== getCacheName())
                    .map(name => caches.delete(name))
            );
            self.clients.claim();
        })()
    );
});

// Fetch: cache-first for app shell and data, network-first for manifest
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Skip non-GET
    if (event.request.method !== 'GET') return;

    // Skip external URLs
    if (url.origin !== location.origin) return;

    // Network-first for manifest (to get fresh version)
    if (url.pathname.endsWith('manifest.json')) {
        event.respondWith(
            (async () => {
                try {
                    const networkRes = await fetch(event.request);
                    const cache = await caches.open(getCacheName());
                    cache.put(event.request, networkRes.clone());
                    return networkRes;
                } catch (e) {
                    const cached = await caches.match(event.request);
                    if (cached) return cached;
                    throw e;
                }
            })()
        );
        return;
    }

    // Cache-first for everything else
    event.respondWith(
        (async () => {
            const cached = await caches.match(event.request);
            if (cached) return cached;

            const networkRes = await fetch(event.request);

            // Cache successful responses for data files
            if (networkRes.ok && (
                url.pathname.includes('/data/') ||
                APP_SHELL.some(path => url.pathname.endsWith(path.replace('./', '/')))
            )) {
                const cache = await caches.open(getCacheName());
                cache.put(event.request, networkRes.clone());
            }

            return networkRes;
        })()
    );
});
