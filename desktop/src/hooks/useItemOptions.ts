import { useMemo } from "react";
import { useApp } from "../store/useApp";
import { itemStatus, num } from "../lib/format";

export function useItemOptions() {
  const { state } = useApp();
  return useMemo(
    () => state.items.map((item) => ({
      value: item.id,
      label: `${item.name} · ${num(item.qty)} ${item.unit}`,
      status: itemStatus(item),
    })),
    [state.items]
  );
}
