/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />
// Makes the app installable and lets the shell start offline. API calls are never cached:
// time tracking data must always come from the server.
import { assets, immutable } from '$app/manifest';
import { version } from '$app/env';

const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = `pendel-${version}`;
// Manifest paths are relative to the base path, which is the site root here
const ASSETS = [
	...immutable.map((f) => `/${f.path}`),
	...assets.map((f) => `/${f.path}`).filter((p) => !p.endsWith('.webmanifest')),
	'/'
];

sw.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(ASSETS))
			.then(() => sw.skipWaiting())
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
			.then(() => sw.clients.claim())
	);
});

sw.addEventListener('fetch', (event) => {
	const { request } = event;
	const url = new URL(request.url);
	if (request.method !== 'GET' || url.origin !== sw.location.origin || url.pathname.startsWith('/api/')) return;

	// Navigations: network first (fresh index.html after deploys), cached shell when offline
	if (request.mode === 'navigate') {
		event.respondWith(fetch(request).catch(async () => (await caches.match('/')) ?? Response.error()));
		return;
	}
	// Static assets: cache first (file names are content-hashed)
	event.respondWith(caches.match(request).then((hit) => hit ?? fetch(request)));
});
