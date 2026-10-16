import { goto } from '$app/navigation';

/** Routes that work without a login (the layout doesn't gate them, 401s don't redirect). */
export const PUBLIC_ROUTES = ['/login', '/setup', '/invite'];

export const isPublicPath = (path: string) => PUBLIC_ROUTES.some((p) => path.startsWith(p));

export class ApiError extends Error {
	constructor(
		public status: number,
		public detail: string
	) {
		super(detail);
	}
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const headers: Record<string, string> = { 'X-Requested-With': 'pendel' };
	if (body !== undefined) headers['Content-Type'] = 'application/json';
	const res = await fetch(`/api${path}`, {
		method,
		headers,
		body: body === undefined ? undefined : JSON.stringify(body),
		credentials: 'same-origin'
	});
	if (res.status === 204) return undefined as T;
	const data = await res.json().catch(() => ({}));
	if (!res.ok) {
		const detail = typeof data.detail === 'string' ? data.detail : 'validation_error';
		if (res.status === 401 && detail === 'not_authenticated' && !isPublicPath(location.pathname)) goto('/login');
		throw new ApiError(res.status, detail);
	}
	return data as T;
}

export const api = {
	get: <T>(path: string, params?: Record<string, string>) =>
		request<T>('GET', params ? `${path}?${new URLSearchParams(params)}` : path),
	post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
	put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
	patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
	del: (path: string) => request<void>('DELETE', path)
};
