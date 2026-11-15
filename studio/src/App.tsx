import { useEffect, useState } from "react";
import { type AuthStatus, authStatus, logout, me, type Person } from "./api";
import Account from "./pages/Account";
import Items from "./pages/Items";
import ItemView from "./pages/ItemView";
import Login from "./pages/Login";
import Measurements from "./pages/Measurements";
import People from "./pages/People";
import Status from "./pages/Status";
import { go, useRoute } from "./router";

/** The studio: sign in, then work items (manual drafting), people, measurements. */
export default function App() {
  const route = useRoute();
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [user, setUser] = useState<Person | null | undefined>(undefined);

  useEffect(() => {
    authStatus().then(setStatus).catch(() => setStatus(null));
    me()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  if (route[0] === "status") return <Status />;
  if (user === undefined || status === null)
    return <p className="p-6 font-sans text-slate-500">Loading…</p>;
  if (user === null)
    return (
      <Login
        status={status}
        onIn={(p) => {
          setUser(p);
          go("items");
        }}
      />
    );

  const signOut = async () => {
    await logout();
    setStatus(await authStatus()); // the owner may have been made since the page loaded
    setUser(null);
  };
  const pages = ["items", "measurements", "account", ...(user.role === "owner" ? ["people"] : [])];
  const page = pages.includes(route[0] ?? "") ? route[0] : "items";
  const tab = (path: string, label: string) => (
    <a href={`#/${path}`} className={page === path ? "font-semibold" : "text-slate-600 hover:text-slate-900"}>
      {label}
    </a>
  );

  return (
    <div className="min-h-screen font-sans text-slate-900">
      <nav className="flex h-12 items-center gap-5 border-b px-4 text-sm">
        <button onClick={() => go("items")} className="font-semibold">yoko studio</button>
        {tab("items", "Work items")}
        {tab("measurements", "Measurements")}
        {user.role === "owner" && tab("people", "People")}
        <span className="flex-1" />
        {tab("status", "Status")}
        {tab("account", user.name)}
        <button onClick={signOut} className="text-slate-600 hover:text-slate-900">Sign out</button>
      </nav>
      {page === "items" && route[1] ? <ItemView id={Number(route[1])} /> : null}
      {page === "items" && !route[1] ? <Items /> : null}
      {page === "measurements" && <Measurements />}
      {page === "people" && user.role === "owner" && <People />}
      {page === "account" && <Account />}
    </div>
  );
}
