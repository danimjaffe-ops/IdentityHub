import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiRequestError } from "./client";

function stubFetch(res: Partial<Response>) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(res));
}

describe("api client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns parsed JSON on success", async () => {
    stubFetch({ ok: true, status: 200, json: async () => ({ hello: "world" }) } as Response);
    await expect(api.get("/x")).resolves.toEqual({ hello: "world" });
  });

  it("returns undefined on 204 No Content", async () => {
    stubFetch({
      ok: true,
      status: 204,
      json: async () => {
        throw new Error("no body");
      },
    } as unknown as Response);
    await expect(api.delete("/x")).resolves.toBeUndefined();
  });

  it("sends credentials and a JSON content-type", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);
    await api.post("/x", { a: 1 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/x");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ a: 1 }));
  });

  it("throws ApiRequestError carrying the parsed error fields", async () => {
    stubFetch({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({
        error: "validation_error",
        message: "bad input",
        details: { email: ["required"] },
      }),
    } as Response);

    const err = (await api.post("/x", {}).catch((e) => e)) as ApiRequestError;
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err.status).toBe(400);
    expect(err.error).toBe("validation_error");
    expect(err.message).toBe("bad input");
    expect(err.details).toEqual({ email: ["required"] });
  });

  it("falls back to statusText when the error body isn't JSON", async () => {
    stubFetch({
      ok: false,
      status: 500,
      statusText: "Server Error",
      json: async () => {
        throw new Error("not json");
      },
    } as unknown as Response);

    const err = (await api.get("/x").catch((e) => e)) as ApiRequestError;
    expect(err.error).toBe("unknown");
    expect(err.message).toBe("Server Error");
  });

  it("dispatches an auth:unauthorized event on any 401", async () => {
    stubFetch({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: async () => ({ error: "session_expired", message: "expired" }),
    } as Response);

    const handler = vi.fn();
    window.addEventListener("auth:unauthorized", handler as EventListener);
    await api.get("/x").catch(() => {});
    window.removeEventListener("auth:unauthorized", handler as EventListener);

    expect(handler).toHaveBeenCalledOnce();
    expect((handler.mock.calls[0][0] as CustomEvent).detail).toBe("session_expired");
  });
});
