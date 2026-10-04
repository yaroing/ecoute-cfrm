let auth = JSON.parse(sessionStorage.getItem("ecoute-session") || "null");
export const setAuth = (value) => {
  auth = value;
  if (value) sessionStorage.setItem("ecoute-session", JSON.stringify(value));
  else sessionStorage.removeItem("ecoute-session");
};
export const getAuth = () => auth;
let renewal = null;
export async function api(path, options = {}) {
  const sentToken = auth?.token;
  const response = await fetch("/api/v1" + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(auth ? { Authorization: `Bearer ${auth.token}` } : {}),
      ...options.headers,
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (response.status === 401 && auth && !options.retried) {
    if (auth.token !== sentToken) return api(path, { ...options, retried: true });
    if (!renewal) {
      renewal = fetch("/api/v1/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: auth.refresh }),
      }).then(async renewed => {
        if (!renewed.ok) return false;
        setAuth(await renewed.json());
        return true;
      }).finally(() => { renewal = null; });
    }
    if (await renewal) {
      return api(path, { ...options, retried: true });
    }
    setAuth(null);
    window.dispatchEvent(new Event("session-expired"));
  }
  if (!response.ok) {
    let problem;
    try {
      problem = await response.json();
    } catch {
      problem = { detail: `Erreur serveur (${response.status})` };
    }
    throw new Error(
      typeof (problem.detail?.detail ?? problem.detail) === "string"
        ? (problem.detail?.detail ?? problem.detail)
        : JSON.stringify(problem.detail ?? problem),
    );
  }
  if (response.status === 204) return null;
  if (options.blob) return response.blob();
  return response.json();
}
export const post = (path, body) => api(path, { method: "POST", body });
