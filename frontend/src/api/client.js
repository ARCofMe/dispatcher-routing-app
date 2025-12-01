import axios from "axios";
const api = axios.create({ baseURL: "http://localhost:5000/api" });
export const fetchTechs=()=>api.get("/techs").then(r=>r.data);
export const fetchRoutePreview=(t,d,origin, destination)=>api.get("/route/preview",{params:{tech_id:t,date:d,origin,destination}}).then(r=>r.data);
export const simulateRoute=(p)=>api.post("/route/simulate",p).then(r=>r.data);
export const commitRoute=(p)=>api.post("/route/commit",p).then(r=>r.data);
export default api;
