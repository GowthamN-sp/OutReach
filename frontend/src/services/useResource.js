import { useCallback, useEffect, useRef, useState } from "react";

// Memory only, cleared on account changes. Never persist private workspace data.
const cache = new Map();
let epoch = 0;
export function clearResources() {
  epoch += 1;
  cache.clear();
}

export default function useResource(key, loader, dependencies = []) {
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const generation = useRef(0);
  const [state, setState] = useState(() => ({
    key,
    data: cache.get(key),
    loading: true,
    error: "",
  }));
  const load = useCallback(async () => {
    const request = ++generation.current;
    const started = epoch;
    setState((previous) => ({
      key,
      data: previous.key === key ? previous.data : cache.get(key),
      loading: true,
      error: "",
    }));
    try {
      const data = await loaderRef.current();
      if (request === generation.current && started === epoch) {
        cache.set(key, data);
        setState({ key, data, loading: false, error: "" });
      }
      return data;
    } catch (error) {
      if (request === generation.current && started === epoch) {
        setState((previous) => ({
          ...previous,
          loading: false,
          error: error.message,
        }));
      }
      return undefined;
    }
  }, [key]);
  useEffect(() => {
    load();
    return () => {
      generation.current += 1;
    };
  }, [load, ...dependencies]);
  return {
    ...(state.key === key
      ? state
      : { data: cache.get(key), loading: true, error: "" }),
    load,
  };
}
