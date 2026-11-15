import { useEffect, useState } from "react";
import {
  finishItem,
  getItem,
  type Item,
  itemObject,
  itemScene,
  itemSizes,
  type ObjectInfo,
  type Scene,
  type SizeChoice,
} from "../api";
import Canvas from "../components/Canvas";
import Inspector from "../components/Inspector";

/** One work item: the pattern on the canvas, at any size; click an object to inspect it.
 * Stage A is read-only: drafting comes in stage B. */
export default function ItemView({ id }: { id: number }) {
  const [item, setItem] = useState<Item | null>(null);
  const [sizes, setSizes] = useState<SizeChoice[]>([]);
  const [size, setSize] = useState<string>("");
  const [scene, setScene] = useState<Scene | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [info, setInfo] = useState<ObjectInfo | null>(null);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [labels, setLabels] = useState(true);
  const [landmarks, setLandmarks] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fitAll, setFitAll] = useState(false);
  const [fitKey, setFitKey] = useState(0);

  useEffect(() => {
    getItem(id).then(setItem).catch((e: Error) => setError(e.message));
    itemSizes(id)
      .then((s) => {
        setSizes(s.sizes);
        setSize(s.default);
      })
      .catch((e: Error) => setError(e.message));
  }, [id]);
  useEffect(() => {
    if (!size) return;
    itemScene(id, size).then(setScene).catch((e: Error) => setError(e.message));
  }, [id, size]);
  useEffect(() => {
    if (selected === null) {
      setInfo(null);
      return;
    }
    setLoadingInfo(true);
    itemObject(id, selected, size)
      .then(setInfo)
      .catch(() => setInfo(null))
      .finally(() => setLoadingInfo(false));
  }, [id, selected, size]);

  if (error) return <p className="p-6 text-red-700">{error}</p>;
  if (!item) return <p className="p-6 text-slate-500">Loading…</p>;
  const finish = async () => {
    if (!window.confirm("Finish this item? You cannot edit it afterwards.")) return;
    await finishItem(id);
    setItem(await getItem(id));
  };

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col">
      <header className="flex flex-wrap items-center gap-4 border-b px-4 py-2 text-sm">
        <div>
          <span className="font-semibold">{item.title}</span>{" "}
          <span className="text-slate-500">
            {item.kind === "recipe_example" ? `${item.recipe} · example ${item.example_no}` : "design"} ·{" "}
            {item.author} · {item.status}
          </span>
        </div>
        <label className="flex items-center gap-1">
          Size
          <select value={size} onChange={(e) => setSize(e.target.value)} className="rounded border px-1 py-0.5"
            data-testid="size">
            {sizes.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={labels} onChange={(e) => setLabels(e.target.checked)} /> Labels
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={landmarks} onChange={(e) => setLandmarks(e.target.checked)} />
          Proposed landmark names
        </label>
        <button className="rounded border px-2 py-0.5" onClick={() => { setFitAll(false); setFitKey((k) => k + 1); }}>
          Fit {item.pieces.length ? "the item's pieces" : "pattern"}
        </button>
        <button className="rounded border px-2 py-0.5" onClick={() => { setFitAll(true); setFitKey((k) => k + 1); }}>
          Fit everything
        </button>
        {scene && scene.errors.length > 0 && (
          <span className="text-red-700">{scene.errors.length} formula errors at this size</span>
        )}
        <span className="flex-1" />
        {item.can_edit && (
          <button onClick={finish} className="rounded border px-2 py-1">Finish item</button>
        )}
      </header>
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1">
          {scene ? (
            <Canvas scene={scene} selected={selected} onSelect={setSelected}
              showLabels={labels} showLandmarks={landmarks}
              fitTo={fitAll || !scene.focus ? scene.bounds : scene.focus} fitKey={fitKey} />
          ) : (
            <p className="p-6 text-slate-500">Drawing…</p>
          )}
        </div>
        <aside className="w-80 shrink-0 overflow-y-auto border-l bg-slate-50">
          <Inspector info={info} loading={loadingInfo} onSelect={setSelected} />
        </aside>
      </div>
    </div>
  );
}
