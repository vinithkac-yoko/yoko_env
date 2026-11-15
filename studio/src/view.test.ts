import { describe, expect, it } from "vitest";
import { fit, pan, toPattern, zoomAt } from "./view";

describe("the canvas view", () => {
  it("fits the pattern with a margin and the drawing area's shape", () => {
    const v = fit({ min_x: 0, min_y: 0, max_x: 100, max_y: 50 }, 2, 0);
    expect(v).toEqual({ x: 0, y: 0, w: 100, h: 50 });
    const tall = fit({ min_x: 0, min_y: 0, max_x: 100, max_y: 50 }, 1, 0);
    expect(tall.w).toBe(100);
    expect(tall.h).toBe(100);
    expect(tall.y).toBe(-25); // centred
  });

  it("zooms about the point under the cursor", () => {
    const v = { x: 0, y: 0, w: 100, h: 100 };
    const z = zoomAt(v, 2, 50, 50);
    expect(z).toEqual({ x: 25, y: 25, w: 50, h: 50 });
    const corner = zoomAt(v, 2, 0, 0);
    expect(corner.x).toBe(0);
    expect(corner.y).toBe(0);
  });

  it("pans by screen pixels and converts screen to pattern", () => {
    const v = { x: 0, y: 0, w: 200, h: 100 };
    expect(pan(v, 10, 0, 100)).toEqual({ x: -20, y: 0, w: 200, h: 100 });
    expect(toPattern(v, 50, 25, 100)).toEqual([100, 50]);
  });
});
