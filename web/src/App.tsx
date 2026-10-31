import { useEffect, useState } from "react";
import { Camera } from "./pages/Camera";
import { Operator } from "./pages/Operator";
import { Phone } from "./pages/Phone";
import { Supervisor } from "./pages/Supervisor";

const PAGES = { "": Operator, camera: Camera, phone: Phone, supervisor: Supervisor };
type Route = keyof typeof PAGES;

const route = (): Route => {
  const name = location.hash.replace("#/", "");
  return name in PAGES ? (name as Route) : "";
};

export function App() {
  const [page, setPage] = useState(route);

  useEffect(() => {
    const onChange = () => setPage(route());
    addEventListener("hashchange", onChange);
    return () => removeEventListener("hashchange", onChange);
  }, []);

  const Page = PAGES[page];
  return (
    <>
      <nav className="nav">
        <a href="#/" className={page === "" ? "on" : ""}>
          Operator
        </a>
        <a href="#/camera" className={page === "camera" ? "on" : ""}>
          Camera
        </a>
        <a href="#/phone" className={page === "phone" ? "on" : ""}>
          Phone
        </a>
        <a href="#/supervisor" className={page === "supervisor" ? "on" : ""}>
          Supervisor
        </a>
      </nav>
      <Page />
    </>
  );
}
