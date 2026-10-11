import { describe, expect, it } from "vitest";
import { flattenTree, shortSha, type TreeNode } from "./api";

describe("shortSha", () => {
  it("shortens to 7 chars", () => {
    expect(shortSha("0627ac315f7b9aae")).toBe("0627ac3");
  });
});

describe("flattenTree", () => {
  const leaf = (id: string): TreeNode => ({
    id,
    name: id,
    area: "styles",
    garment_type: "",
    tags: [],
    children: [],
  });

  it("lists a pattern before its styles, with their depth", () => {
    const base: TreeNode = { ...leaf("base"), area: "base", children: [{ ...leaf("skirt"), children: [leaf("pencil")] }] };
    expect(flattenTree([base]).map((r) => [r.node.id, r.depth])).toEqual([
      ["base", 0],
      ["skirt", 1],
      ["pencil", 2],
    ]);
  });
});
