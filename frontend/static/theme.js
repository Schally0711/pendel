// Applies the colour theme before the app renders (no flash). Choice per device in localStorage:
// 'system' (default), 'light' or 'dark'. Printing always uses the light theme.
(function () {
	var KEY = 'pendel-theme';
	var media = window.matchMedia('(prefers-color-scheme: dark)');
	function stored() {
		try {
			return localStorage.getItem(KEY) || 'system';
		} catch (e) {
			return 'system';
		}
	}
	function apply() {
		var mode = stored();
		var dark = mode === 'dark' || (mode === 'system' && media.matches);
		document.documentElement.dataset.theme = dark ? 'dark' : 'light';
		var meta = document.querySelector('meta[name="theme-color"]');
		if (meta) meta.setAttribute('content', dark ? '#020617' : '#0f766e');
	}
	window.pendelTheme = {
		get: stored,
		set: function (mode) {
			try {
				if (mode === 'system') localStorage.removeItem(KEY);
				else localStorage.setItem(KEY, mode);
			} catch (e) {}
			apply();
		}
	};
	media.addEventListener('change', apply);
	window.addEventListener('beforeprint', function () {
		document.documentElement.dataset.theme = 'light';
	});
	window.addEventListener('afterprint', apply);
	apply();
})();
