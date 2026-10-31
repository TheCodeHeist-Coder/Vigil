import { useEffect, useState } from "react";
import { AppBar, type Route } from "./components/AppBar";
import { Camera } from "./pages/Camera";
import { Operator } from "./pages/Operator";
import { Phone } from "./pages/Phone";
import { Supervisor } from "./pages/Supervisor";
import { useStatus } from "./status";

const PAGES = { "": Operator, camera: Camera, phone: Phone, supervisor: Supervisor };

const route = (): Route => {
  const name = location.hash.replace("#/", "");
  return name in PAGES ? (name as Route) : "";
};

export function App() {
  const [page, setPage] = useState(route);
  const status = useStatus();

  useEffect(() => {
    const onChange = () => setPage(route());
    addEventListener("hashchange", onChange);
    return () => removeEventListener("hashchange", onChange);
  }, []);

  const Page = PAGES[page];
  return (
    <>
      <AppBar page={page} status={status} />
      <Page />
    </>
  );
}
