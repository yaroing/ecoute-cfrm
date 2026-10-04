import { openDB } from "idb";
const db = () =>
  openDB("ecoute-queue", 1, {
    upgrade(db) {
      db.createObjectStore("returns", { keyPath: "key" });
    },
  });
export const queued = async () => (await db()).getAll("returns");
export const enqueue = async (value) => (await db()).put("returns", value);
export const remove = async (key) => (await db()).delete("returns", key);
export const clearQueue = async () => (await db()).clear("returns");
export async function requireEmptyQueue() {
  if ((await queued()).length) {
    throw new Error(
      "Des retours attendent leur transmission. Synchronisez la file ou supprimez explicitement les saisies avant de vous déconnecter.",
    );
  }
}
export function sensitiveText(text, keywords) {
  return keywords.some((word) =>
    text.toLocaleLowerCase().includes(word.toLocaleLowerCase()),
  );
}
export function segments(text) {
  const gsm =
    /^[A-Za-z0-9 @£$¥èéùìòÇ\n\rØøÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&'()*+,\-./:;<=>?¡ÄÖÑÜ§¿äöñüà^{}\\[\]~|€]*$/;
  const unicode = !gsm.test(text);
  const length = unicode
    ? text.length
    : [...text].reduce((n, c) => n + ("^{}\\[]~|€".includes(c) ? 2 : 1), 0);
  return {
    unicode,
    count: length
      ? Math.ceil(
          length /
            (length > (unicode ? 70 : 160)
              ? unicode
                ? 67
                : 153
              : unicode
                ? 70
                : 160),
        )
      : 0,
    length,
  };
}
