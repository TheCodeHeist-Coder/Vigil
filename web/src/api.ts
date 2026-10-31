async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) throw new Error(`${path} failed: ${response.status} ${await response.text()}`);
  return response.json();
}

export const get = <T,>(path: string) => call<T>(path);
export const post = <T,>(path: string, body: unknown) => call<T>(path, { method: "POST", body: JSON.stringify(body) });
export const put = <T,>(path: string, body: unknown) => call<T>(path, { method: "PUT", body: JSON.stringify(body) });
