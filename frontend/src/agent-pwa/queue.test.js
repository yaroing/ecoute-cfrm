import { describe, it, expect } from "vitest";
import { sensitiveText, segments } from "./queue";
import "fake-indexeddb/auto";
import { enqueue, queued, remove, clearQueue } from "./queue";
import { requireEmptyQueue } from "./queue";
describe("protection terrain et compteurs SMS", () => {
  it("détecte les mots-clés sans tenir compte de la casse", () => {
    expect(sensitiveText("Une FRAUDE à signaler", ["fraude"])).toBe(true);
    expect(sensitiveText("Une suggestion", ["fraude"])).toBe(false);
  });
  it("compte GSM-7 et les caractères étendus", () => {
    expect(segments("a".repeat(160)).count).toBe(1);
    expect(segments("a".repeat(161)).count).toBe(2);
    expect(segments("^".repeat(81)).count).toBe(2);
  });
  it("compte UCS-2 et les paires de substitution", () => {
    expect(segments("漢".repeat(70)).count).toBe(1);
    expect(segments("漢".repeat(71)).count).toBe(2);
    expect(segments("🙂".repeat(36)).count).toBe(2);
  });
  it("conserve les entrées non confirmées lors de trois interruptions et efface à la déconnexion", async () => {
    await clearQueue();
    for (let i = 0; i < 100; i++)
      await enqueue({
        key: "local-" + i,
        text: "Retour ordinaire " + i,
        agent: 1,
      });
    expect((await queued()).length).toBe(100);
    for (let batch = 0; batch < 3; batch++) {
      const pending = await queued();
      for (const item of pending.slice(0, 20)) await remove(item.key);
      // An interruption leaves the rest intact; retrying an unconfirmed key overwrites rather than duplicates.
      for (const item of pending.slice(20)) await enqueue(item);
      expect((await queued()).length).toBe(100 - (batch + 1) * 20);
    }
    await clearQueue();
    expect(await queued()).toEqual([]);
  });
  it("bloque la déconnexion sans perdre la file lors de trois accusés interrompus", async () => {
    await clearQueue();
    for (let i = 0; i < 30; i++)
      await enqueue({ key: "os4-" + i, text: "FICTIF retour " + i });
    await expect(requireEmptyQueue()).rejects.toThrow("transmission");
    expect((await queued()).length).toBe(30);
    for (let i = 30; i < 100; i++)
      await enqueue({ key: "os4-" + i, text: "FICTIF retour " + i });
    for (let interruption = 0; interruption < 3; interruption++) {
      const pending = await queued();
      // The server accepted the batch, but its acknowledgment did not arrive.
      for (const item of pending) await enqueue(item);
      expect((await queued()).length).toBe(100);
      await expect(requireEmptyQueue()).rejects.toThrow("transmission");
    }
    for (const item of (await queued()).slice(0, 30)) await remove(item.key);
    expect((await queued()).length).toBe(70);
    await expect(requireEmptyQueue()).rejects.toThrow("transmission");
    for (const item of await queued()) await remove(item.key);
    await expect(requireEmptyQueue()).resolves.toBeUndefined();
  });
});
