import axios from "axios";

const api = axios.create({ baseURL: "http://localhost:5000/api" });

const STORAGE_KEYS = {
  apiKey: "bfApiKey",
  account: "bfAccount",
};

const readStoredCreds = () => ({
  apiKey: localStorage.getItem(STORAGE_KEYS.apiKey) || "",
  account: localStorage.getItem(STORAGE_KEYS.account) || "",
});

export const getBlueFolderCredentials = () => ({
  apiKey: localStorage.getItem(STORAGE_KEYS.apiKey) || "",
  account: localStorage.getItem(STORAGE_KEYS.account) || "",
});

export const setBlueFolderCredentials = (apiKey, account) => {
  if (apiKey) localStorage.setItem(STORAGE_KEYS.apiKey, apiKey);
  if (account) localStorage.setItem(STORAGE_KEYS.account, account);
  applyCredHeaders({ apiKey, account });
};

const applyCredHeaders = ({ apiKey, account }) => {
  if (apiKey && account) {
    api.defaults.headers.common["X-BF-API-KEY"] = apiKey;
    api.defaults.headers.common["X-BF-ACCOUNT"] = account;
  } else {
    delete api.defaults.headers.common["X-BF-API-KEY"];
    delete api.defaults.headers.common["X-BF-ACCOUNT"];
  }
};

// Apply saved creds on load
applyCredHeaders(getBlueFolderCredentials());

// Always re-apply latest creds before each request (covers multi-tab changes).
api.interceptors.request.use((config) => {
  const { apiKey, account } = readStoredCreds();
  if (apiKey && account) {
    config.headers = config.headers || {};
    config.headers["X-BF-API-KEY"] = apiKey;
    config.headers["X-BF-ACCOUNT"] = account;
  }
  return config;
});

export const fetchTechs = (creds) => {
  const apiKey = creds?.apiKey || readStoredCreds().apiKey;
  const account = creds?.account || readStoredCreds().account;
  return api
    .get("/techs", {
      headers: apiKey && account ? { "X-BF-API-KEY": apiKey, "X-BF-ACCOUNT": account } : undefined,
      params: apiKey && account ? { api_key: apiKey, account } : undefined,
    })
    .then((r) => r.data);
};
export const fetchRoutePreview = (t, d, origin, destination, optimize) =>
  api
    .get("/route/preview", { params: { tech_id: t, date: d, origin, destination, optimize } })
    .then((r) => r.data);
export const simulateRoute = (p) => api.post("/route/simulate", p).then((r) => r.data);
export const commitRoute = (p) => api.post("/route/commit", p).then((r) => r.data);
export default api;
