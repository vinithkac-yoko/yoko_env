import { describe, expect, it } from "vitest";
import { shortSha } from "./api";

describe("shortSha", () => {
  it("shortens to 7 chars", () => {
    expect(shortSha("0627ac315f7b9aae")).toBe("0627ac3");
  });
});
