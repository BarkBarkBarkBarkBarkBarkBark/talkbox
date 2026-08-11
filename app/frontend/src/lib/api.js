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
  admin: {
    currentUser: () => request("/api/users/me"),
    login: (email, password) => request("/api/auth/jwt/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    }),
    logout: () => request("/api/auth/jwt/logout", { method: "POST" }),
    agencies: ({ search = "", category = "", page = 1 } = {}) => {
      const params = new URLSearchParams({ page: String(page) });
      if (search) params.set("search", search);
      if (category) params.set("category", category);
      return request(`/api/admin/agencies?${params}`);
    },
    categories: () => request("/api/admin/categories"),
    createAgency: (agency) => request("/api/admin/agencies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(agency),
    }),
    updateAgency: (id, agency) => request(`/api/admin/agencies/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(agency),
    }),
    bulkUpdateAgencies: (changes) => request("/api/admin/agencies/bulk", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
    deleteAgency: (id) => request(`/api/admin/agencies/${id}`, { method: "DELETE" }),
    previewImport: (file) => {
      const data = new FormData();
      data.append("file", file);
      return request("/api/admin/imports", { method: "POST", body: data });
    },
    importRows: (id) => request(`/api/admin/imports/${id}`),
    publishImport: (id) => request(`/api/admin/imports/${id}/publish`, { method: "POST" }),
    discardImport: (id) => request(`/api/admin/imports/${id}/discard`, { method: "POST" }),
    exportAgencies: async () => {
      const response = await fetch(`${BASE_URL}/api/admin/agencies/export`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error(`Export failed: HTTP ${response.status}`);
      return response.blob();
    },
  },
};

export async function postQuery(q) {
  return api.query(q);
}
