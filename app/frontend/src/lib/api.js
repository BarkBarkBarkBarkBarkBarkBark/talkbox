const BASE_URL = import.meta.env.VITE_API_URL || "";

async function request(path, opts = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: "include",
    ...opts,
  });

  if (res.status === 204) return null;

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = {};
  }

  if (!res.ok) {
    const err = new Error(data?.detail || data?.error || `HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

export const api = {
  query: (q) =>
    request("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q }),
    }),
};

export async function postQuery(q) {
  return api.query(q);
}
