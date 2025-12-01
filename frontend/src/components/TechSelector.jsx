import { useEffect,useState } from "react";
import { fetchTechs } from "../api/client";
export default function TechSelector({value,onChange}) {
  const [techs,setTechs]=useState([]);
  useEffect(()=>{fetchTechs().then(setTechs)},[]);
  return <select value={value||""} onChange={e=>onChange(Number(e.target.value))}>
    <option value="">Select technician…</option>
    {techs.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}
  </select>;
}
