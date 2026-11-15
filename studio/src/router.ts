import { useEffect, useState } from "react";

/** The page, from the address's hash: "#/items/3" -> ["items", "3"]. */
export function useRoute(): string[] {
  const read = () => window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [route, setRoute] = useState<string[]>(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export function go(path: string): void {
  window.location.hash = path.startsWith("#") ? path : `#/${path.replace(/^\//, "")}`;
}
